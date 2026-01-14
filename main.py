import cv2
import asyncio
import os
import time
from datetime import datetime
import json
import pathlib
import yaml
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Body, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import piexif # Import piexif
from PIL import Image, ImageDraw, ImageFont # Import PIL for overlay
import sys  # Import sys
import socket # Import socket
from typing import Optional

# Import camera handling logic
from camera_handler import detect_cameras, USBCamera, PiCamera
from config_handler import (
    load_config, generate_default_config, save_config, 
    load_mqtt_config, save_mqtt_config
)
from mqtt_handler import MQTTClientWrapper
from system_monitor import get_system_stats

# --- Constants ---
# Define a safe base directory for all captures
CAPTURE_DIR_BASE = pathlib.Path(__file__).parent.absolute() / "captures"

from contextlib import asynccontextmanager

# --- App Lifespan Management ---
# --- Global MQTT Callback ---
# --- Global MQTT Callback ---
async def mqtt_log_callback(message):
    await manager.broadcast({
        "type": "mqtt_log",
        "message": message
    })

async def mqtt_callback(data):
    original_data = data.copy() # Keep original for logging
    
    # Modify data based on context
    # active_camera_context and active_cameras are globals
    if active_camera_context and active_camera_context in active_cameras:
            # Context is set to a valid, active camera. 
            print(f"[{'MQTT'}] Context active: {active_camera_context}. Filtering capture.", file=sys.stderr)
            
            param_resolution = data.get('resolution', None)
            
            single_cap_request = PerCameraCaptureSettings(
                camera_path=active_camera_context,
                resolution=param_resolution
            )
            
            # Load saved defaults (Prefix)
            saved_defaults = {}
            try:
                 full_config = load_config()
                 saved_defaults = full_config.get('defaults', {})
            except:
                 pass

            prefix_val = data.get('prefix')
            if not prefix_val and 'prefix' in saved_defaults:
                 prefix_val = saved_defaults['prefix']
            if not prefix_val: 
                 prefix_val = 'IMG'

            request = CaptureAllRequest(
                captures=[single_cap_request],
                prefix=prefix_val
            )
    else:
        # Global context (Multi-cam) or invalid context
        print(f"[{'MQTT'}] Global context. Capturing all.", file=sys.stderr)
        
        # Load saved defaults (Prefix)
        saved_defaults = {}
        try:
             full_config = load_config()
             saved_defaults = full_config.get('defaults', {})
        except Exception as e:
             print(f"Error loading defaults for MQTT: {e}", file=sys.stderr)

        # If prefix is not in data (or is None), try to use saved default
        if 'prefix' not in data or data['prefix'] is None:
             if 'prefix' in saved_defaults:
                  data['prefix'] = saved_defaults['prefix']

        request = CaptureAllRequest(**data)

    print(f"Triggering capture via MQTT with data: {original_data} -> Context: {active_camera_context}", file=sys.stderr)
    try:
        captured_files = await perform_global_capture(request, source="MQTT")
        
        # Send confirmation if capture was successful
        if captured_files:
            confirmation_payload = {
                "status": "success",
                "request_id": original_data.get("request_id"), # Echo request_id if present
                "files": [str(pathlib.Path(f).name) for f in captured_files],
                "count": len(captured_files),
                "timestamp": time.time()
            }
            if mqtt_client:
                hostname = socket.gethostname()
                mqtt_client.publish(f"dataset_collector/{hostname}/capture/finished", json.dumps(confirmation_payload))

    except Exception as e:
        print(f"Error handling MQTT message: {e}", file=sys.stderr)






@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    """
    # --- Startup ---
    global available_cameras
    global system_config # Declare system_config as global
    print("--- DETECTING CAMERAS ---")
    try:
        # Load initial config
        system_config = load_config()
        detected_cams = detect_cameras()
        # Update system_config with defaults based on detected cameras
        system_config = generate_default_config(system_config, detected_cams)
        available_cameras = system_config.get('cameras', {})
        print(f"Detected cameras: {available_cameras}")
    except Exception as e:
        print(f"Error during camera detection: {e}", file=sys.stderr)


    # --- MQTT Client Implementation ---
    global mqtt_client
    try:
        mqtt_config = load_mqtt_config()
        mqtt_enabled = mqtt_config.get('enabled', True)
        broker = mqtt_config.get('broker', 'localhost')
        port = mqtt_config.get('port', 1883)
        topic = mqtt_config.get('topic', 'capture/trigger')
        username = mqtt_config.get('username')
        password = mqtt_config.get('password')
    except Exception as e:
        print(f"Error loading MQTT config: {e}", file=sys.stderr)
        mqtt_enabled = True
        broker = 'localhost'
        port = 1883
        topic = 'capture/trigger'
        username = ''
        password = ''

    # Global context for active camera (set by frontend)
    # None = Multi-camera mode (capture all)
    # "pi_0" = Single camera mode (capture only pi_0)
    global active_camera_context
    active_camera_context = None

    loop = asyncio.get_running_loop()
    hostname = socket.gethostname()
    
    if mqtt_enabled:
        mqtt_client = MQTTClientWrapper(broker, port, topic, mqtt_callback, loop, username, password, mqtt_log_callback, hostname)
        mqtt_client.start()
    else:
        print("MQTT is disabled in config. Skipping startup.", file=sys.stderr)
        mqtt_client = None
    
    yield
    
    # --- Shutdown ---
    if mqtt_client:
        mqtt_client.stop()

    print("Shutting down... stopping all cameras.", file=sys.stderr)
    for camera in active_cameras.values():
        if camera.is_running:
            camera.stop()
    print("All cameras stopped.", file=sys.stderr)


app = FastAPI(lifespan=lifespan)


# --- App State ---
available_cameras = {}
active_cameras = {}
capture_count = 0
pending_transfers = []
mqtt_client = None
interval_capture_running = False
interval_task = None

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        print(f"[WS] Broadcasting message: {message} to {len(self.active_connections)} clients", file=sys.stderr)
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error broadcasting to WS: {e}", file=sys.stderr)

manager = ConnectionManager()
# --- Pydantic Models ---
class CaptureRequest(BaseModel):
    camera_path: str
    subfolder: str | None = "default"
    prefix: str | None = "IMG"
    resolution: str | None = "1280x720"
    shutter_speed: str | None = "Auto"
    iso: int | None = 0 # 0 = Auto
    autofocus: bool | None = None
    manual_focus: float | None = None

class CameraPathRequest(BaseModel):
    camera_path: str

class AutofocusRequest(BaseModel):
    camera_path: str
    enable: bool

class ManualFocusRequest(BaseModel):
    camera_path: str
    focus_value: float

class PerCameraCaptureSettings(BaseModel):
    camera_path: str
    resolution: str | None = None
    shutter_speed: str | None = None
    iso: int | None = None
    autofocus: bool | None = None
    manual_focus: float | None = None
    subfolder: str | None = None
    prefix: str | None = None

class CaptureAllRequest(BaseModel):
    subfolder: str | None = "default"
    prefix: str | None = "IMG"
    resolution: str | None = None
    shutter_speed: str | None = None
    iso: int | None = None
    autofocus: bool | None = None
    captures: list[PerCameraCaptureSettings] | None = None

class StartIntervalRequest(BaseModel):
    interval_seconds: float
    total_count: int = 0 # 0 = infinite
    subfolder: str | None = "interval"
    prefix: str | None = "INT"

class SFTPConfig(BaseModel):
    enabled: bool
    host: str
    port: int = 22
    username: str
    password: str
    remote_path: str
    batch_size: int = 10


# --- Static Files and Templates ---
# --- Static Files and Templates ---
# Ensure capture directory exists before mounting
if not CAPTURE_DIR_BASE.exists():
    CAPTURE_DIR_BASE.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/captures", StaticFiles(directory=CAPTURE_DIR_BASE), name="captures")
templates = Jinja2Templates(directory="templates")

# --- Helper Functions ---
def get_recent_captures(limit: int = 20):
    """Returns a list of recent capture filenames (relative to CAPTURE_DIR_BASE)."""
    image_dir = CAPTURE_DIR_BASE / "images"
    if not image_dir.exists():
        return []
    
    files = []
    for path in image_dir.rglob("*.jpg"):
        files.append(path)
    
    # Sort by modification time, newest first
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    # Return relative paths
    return [str(p.relative_to(CAPTURE_DIR_BASE)) for p in files[:limit]]

@app.get("/api/captures")
async def get_captures():
    return get_recent_captures()
def parse_shutter_speed(shutter_speed_str: str) -> int:
    """Parses a shutter speed string (e.g., '1/100s', 'Auto') into an integer in microseconds."""
    if shutter_speed_str.lower() == 'auto':
        return 0
    try:
        if 's' in shutter_speed_str:
            shutter_speed_str = shutter_speed_str.replace('s', '')
        if '/' in shutter_speed_str:
            numerator, denominator = shutter_speed_str.split('/')
            return int((float(numerator) / float(denominator)) * 1_000_000)
        else:
            return int(shutter_speed_str)
    except (ValueError, ZeroDivisionError):
        return 0

async def perform_global_capture(request: CaptureAllRequest, source: str = "Unknown"):
    """
    Executes the capture logic for all active cameras based on the request.
    This logic is extracted for reuse by API and MQTT.
    """
    if not active_cameras and not available_cameras:
        print(f"[{source}] No active or configured cameras to capture from.", file=sys.stderr)
        return None

    # If active_cameras is empty (e.g. cold start from MQTT), try to populate it from available_cameras
    # This ensures we capture from all known cameras if no specific subset is running
    if not active_cameras:
        print(f"[{source}] No active cameras. Initializing from available_cameras...", file=sys.stderr)
        for cam_path, cam_info in available_cameras.items():
            try:
                if cam_info.get('type') == 'usb':
                     active_cameras[cam_path] = USBCamera(path=cam_info['path'], friendly_name=cam_info['friendly_name'])
                elif cam_info.get('type') == 'pi':
                    active_cameras[cam_path] = PiCamera(
                        camera_id=cam_info['path'],
                        friendly_name=cam_info['friendly_name'],
                        max_width=cam_info.get('max_width'),
                        max_height=cam_info.get('max_height')
                    )
            except Exception as e:
                print(f"Failed to init camera {cam_path}: {e}", file=sys.stderr)


    capture_requests = request.captures
    if not capture_requests:
         # Build capture list from *available_cameras* or active_cameras, prioritizing saved config
        capture_requests = []
        for cam_path in active_cameras.keys():
            # Get default settings from config if available
            cam_config = available_cameras.get(cam_path, {})
            # Use request override OR config value OR defaults
            res = request.resolution or cam_config.get('resolution')
            shutter = request.shutter_speed or cam_config.get('shutter_speed')
            iso = request.iso or cam_config.get('iso')
            af = request.autofocus if request.autofocus is not None else cam_config.get('autofocus_enabled')
            
            capture_requests.append(
                PerCameraCaptureSettings(
                    camera_path=cam_path, 
                    resolution=res, 
                    shutter_speed=shutter,
                    iso=iso,
                    autofocus=af
                )
            )

    original_settings = {}
    captured_files = []
    global capture_count

    try:
        # 1. Determine Settings for All Cameras
        print(f"[{source}] !!! ENTERING CAPTURE SEQUENCE !!!", file=sys.stderr, flush=True)
        print(f"[{source}] Starting capture sequence for cameras: {[r.camera_path for r in capture_requests]}", file=sys.stderr, flush=True)
        
        # 2. Capture Sequentially directly to file (Low Memory Usage)
        for capture_req in capture_requests:
            camera_path = capture_req.camera_path
            
            # Skip if camera not active/found
            if camera_path not in active_cameras:
                 print(f"[{source}] Camera {camera_path} not active. Skipping.", file=sys.stderr)
                 continue

            camera = active_cameras[camera_path]
            cam_config = available_cameras.get(camera_path, {})
            
            # Setup Save Path
            current_subfolder = capture_req.subfolder or request.subfolder
            safe_current_subfolder_name = pathlib.Path(current_subfolder).name or "default" if current_subfolder else "default"
            current_save_dir = CAPTURE_DIR_BASE / "images" / safe_current_subfolder_name
            current_save_dir.mkdir(parents=True, exist_ok=True)
            
            # Determine Resolution FIRST (needed for filename)
            # Priority: Request > Configured Default > Max (if Pi) > Current
            width = None
            height = None
            
            if capture_req.resolution:
                 try:
                     width, height = map(int, capture_req.resolution.split('x'))
                 except ValueError: pass
            
            # If no resolution specified in request, use the current camera resolution
            if not width or not height:
                 if camera.preferred_resolution:
                      width, height = camera.preferred_resolution
                 else:
                      width = camera.width
                      height = camera.height
            
            # Application of Resolution to Camera happens in set_resolution (if strictly needed) 
            # or passed to capture_to_file (transient).

            # Setup Filename with Resolution
            capture_time = int(time.time() * 1000)
            current_prefix_raw = capture_req.prefix or request.prefix or "IMG"
            safe_prefix = "".join(c for c in current_prefix_raw if c.isalnum() or c in ('_', '-')).strip() or "IMG"
            # Format: PREFIX_WxH_CAM_TIME.jpg
            filename = f"{safe_prefix}_{width}x{height}_{camera_path.replace('/', '_')}_{capture_time}.jpg"
            save_path = current_save_dir / filename
            
            # Apply other settings (AF, Shutter)
            if isinstance(camera, PiCamera):
                if capture_req.autofocus is not None:
                     camera.set_autofocus(capture_req.autofocus)
                
                # Sanitize shutter speed
                if capture_req.shutter_speed:
                     s_speed = 0
                     if isinstance(capture_req.shutter_speed, str) and capture_req.shutter_speed.lower() == "auto":
                         s_speed = 0
                     else:
                         try:
                             s_speed = int(capture_req.shutter_speed)
                         except: s_speed = 0
                     camera.set_shutter_speed(s_speed)

                if capture_req.iso is not None:
                     camera.set_iso(capture_req.iso)


            # Perform Capture
            print(f"[{source}] Capturing from {camera_path} to {save_path} (Res: {width}x{height})...", file=sys.stderr)
            try:
                # Ensure camera is running
                if not camera.is_running:
                     camera.start()
                     time.sleep(2) # Warmup

                if isinstance(camera, PiCamera):
                     if capture_req.autofocus:
                          camera.autofocus_and_capture() # Just for AF side effect? no, it returns frame. 
                          # We ignore return. The AF cycle is done.
                          # Actually autofocus_and_capture returns capture_array output.
                          # We just want the AF cycle.
                          # Let's just cycle AF if needed
                          if hasattr(camera.picam2, 'autofocus_cycle'):
                               camera.picam2.autofocus_cycle()
                     
                     # Direct to File Capture (OOM Safe)
                     camera.capture_to_file(str(save_path), width=width, height=height)
                
                else:
                     # USB Camera
                     camera.capture_to_file(str(save_path), width=width, height=height)

                captured_files.append(str(save_path))
                capture_count += 1
                
                # Metadata (Exif) logic - reload file to add exif? 
                # Picamera2 might handle some, but we did manual insertion before.
                # If we want ExposureTime, we need to read metadata.
                # Capture_to_file doesn't return metadata easily unless we access it from picam2 state.
                if isinstance(camera, PiCamera):
                     metadata = camera.picam2.capture_metadata()
                     exposure_time_us = metadata.get('ExposureTime', 0)
                     if exposure_time_us > 0:
                          try:
                              exif_dict = {"Exif": {piexif.ExifIFD.ExposureTime: (exposure_time_us, 1_000_000)}}
                              piexif.insert(piexif.dump(exif_dict), str(save_path))
                          except Exception as e:
                              print(f"Failed to add EXIF: {e}", file=sys.stderr)

                # --- OVERLAY SETTINGS LOGIC ---
                try:
                    # Reload config to ensure we have latest overlay setting
                    current_conf = load_config()
                    if current_conf.get('overlay_settings', False):
                        print(f"[{source}] Applying overlay to {save_path}...", file=sys.stderr)
                        
                        # Open Image
                        with Image.open(str(save_path)) as img:
                            draw = ImageDraw.Draw(img)
                            
                            # Prepare Text
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            res_text = f"{width}x{height}"
                            cam_name = camera.friendly_name
                            
                            # Try to get exposure info if available (PiCamera)
                            exposure_info = ""
                            if isinstance(camera, PiCamera):
                                meta = camera.picam2.capture_metadata() if camera.picam2 else {}
                                exp_time = meta.get('ExposureTime', 0) / 1000000.0 # seconds
                                iso_val = meta.get('AnalogueGain', 0) * 100 # Approx ISO
                                if exp_time > 0:
                                    if exp_time < 1:
                                        exposure_info = f" | 1/{int(1/exp_time)}s"
                                    else:
                                        exposure_info = f" | {exp_time:.1f}s"
                                if iso_val > 0:
                                    exposure_info += f" | ISO {int(iso_val)}"

                            overlay_text = f" {timestamp} | {cam_name} | {res_text}{exposure_info} "
                            
                            # Draw Text - Basic logic, Top Left, White with Black Outline
                            try:
                                font = ImageFont.load_default() 
                            except:
                                font = None
                            
                            text_pos = (20, 20)
                            try:
                                # bbox = draw.textbbox(text_pos, overlay_text, font=font) # specific to newer PIL
                                # fallback for older PIL if needed:
                                text_width, text_height = draw.textsize(overlay_text, font=font)
                                bbox = (text_pos[0], text_pos[1], text_pos[0]+text_width, text_pos[1]+text_height)
                            except AttributeError:
                                # New PIL
                                bbox = draw.textbbox(text_pos, overlay_text, font=font)

                            draw.rectangle((bbox[0]-5, bbox[1]-5, bbox[2]+5, bbox[3]+5), fill="black")
                            draw.text(text_pos, overlay_text, font=font, fill="white")
                            
                            # Save back
                            img.save(str(save_path))
                            print(f"[{source}] Overlay applied.", file=sys.stderr)

                except Exception as e:
                    print(f"[{source}] Failed to apply overlay: {e}", file=sys.stderr)

                # Broadcast
                relative_filename = str(save_path.relative_to(CAPTURE_DIR_BASE))
                await manager.broadcast({
                    "type": "new_file",
                    "filename": relative_filename,
                    "camera_path": camera_path,
                    "source": source
                })

            except Exception as e:
                print(f"[{source}] Capture failed for {camera_path}: {e}", file=sys.stderr)
                # Cleanup partial file
                if save_path.exists() and save_path.stat().st_size == 0:
                     save_path.unlink()

        print(f"[{source}] Capture sequence complete. Total files saved: {len(captured_files)}", file=sys.stderr, flush=True)
        print(f"[{source}] !!! CHECKING SFTP LOGIC !!!", file=sys.stderr, flush=True)

        # --- Auto SFTP Transfer Logic ---
        from sftp_handler import SFTPHandler
        try:
            handler = SFTPHandler()
            is_enabled = handler.config and handler.config.get('enabled', False)
            
            
            global pending_transfers
            
            print(f"[{source}] SFTP Debug: ConfigLoaded={bool(handler.config)}, Enabled={is_enabled}, Captured={len(captured_files)}, PendingBefore={len(pending_transfers)}", file=sys.stderr)

            if is_enabled:
                if captured_files:
                    pending_transfers.extend(captured_files)
                    
                    batch_size = handler.config.get('batch_size', 10)
                    print(f"[{source}] SFTP Check: Pending={len(pending_transfers)}, BatchSize={batch_size}, Enabled={is_enabled}", file=sys.stderr)
                    
                    if len(pending_transfers) >= batch_size:
                        print(f"[{source}] Triggering SFTP transfer for {len(pending_transfers)} files...", file=sys.stderr)
                        batch = list(pending_transfers)
                        pending_transfers.clear()
                        asyncio.create_task(run_sftp_transfer(batch))
            else:
                if pending_transfers:
                    print(f"[{source}] SFTP disabled. Clearing {len(pending_transfers)} pending items.", file=sys.stderr)
                    pending_transfers.clear()
        except Exception as e:
            print(f"Error in SFTP logic: {e}", file=sys.stderr)

    finally:
        # 4. Revert all settings
        print(f"[{source}] Reverting all camera settings...", file=sys.stderr)
        for camera_path, settings in original_settings.items():
            camera = active_cameras.get(camera_path)
            if not camera:
                continue
            
            res = settings.get("resolution")
            if res and (camera.width, camera.height) != res:
                camera.set_resolution(res[0], res[1])

            if isinstance(camera, PiCamera):
                shutter = settings.get("shutter_speed")
                if shutter is not None:
                    camera.set_shutter_speed(shutter)
                
                autofocus = settings.get("autofocus_enabled")
                if autofocus is not None and camera._autofocus_enabled != autofocus:
                     camera.set_autofocus(autofocus)

                iso = settings.get("iso")
                if iso is not None:
                     camera.set_iso(iso)

    return captured_files

async def run_sftp_transfer(file_list):
    """Runs the SFTP transfer in a separate thread/task."""
    from sftp_handler import SFTPHandler
    
    async def _broadcast_deletions(deleted_files):
         if not deleted_files: return
         for fpath in deleted_files:
             try:
                rel_path = str(pathlib.Path(fpath).relative_to(CAPTURE_DIR_BASE))
             except ValueError:
                rel_path = str(pathlib.Path(fpath).name)
                
             await manager.broadcast({
                 "type": "file_deleted",
                 "filename": rel_path
             })

    def _transfer():
        try:
            handler = SFTPHandler()
            if handler.config and handler.config.get('enabled', False): 
                return handler.upload_files(file_list) # Returns list of deleted files
            return []
        except Exception as e:
            print(f"SFTP Transfer Error: {e}", file=sys.stderr)
            return []

    # Run blocking SFTP IO in a thread
    deleted = await asyncio.to_thread(_transfer)
    if deleted:
         await _broadcast_deletions(deleted)

# --- Video Streaming Generator ---
async def stream_generator(camera_path: str, quality: int = 80, max_width: int = 1280):
    camera = active_cameras.get(camera_path)
    if not camera or not camera.is_running:
        print("Camera not active for streaming", file=sys.stderr)
        return

    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]

    while True:
        try:
            frame_rgb = camera.capture_array()
            if frame_rgb is None:
                await asyncio.sleep(0.01)
                continue

            # Smart Downscaling: Resize BEFORE color conversion to save CPU/RAM
            # Check dimensions (height, width, channels)
            h, w = frame_rgb.shape[:2]
            if w > max_width:
                aspect_ratio = w / h
                new_h = int(max_width / aspect_ratio)
                # cv2.resize expects (width, height)
                frame_rgb = cv2.resize(frame_rgb, (max_width, new_h), interpolation=cv2.INTER_AREA)

            if isinstance(camera, PiCamera):
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                flag, encoded_image = cv2.imencode(".jpg", frame_bgr, encode_param)
            else: # USBCamera
                flag, encoded_image = cv2.imencode(".jpg", frame_rgb, encode_param)

            if not flag:
                continue

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encoded_image) + b'\r\n')
            
            # FPS Throttling based on Performance Mode
            perf_mode = system_config.get("_resolved_performance_mode", "high")
            sleep_duration = 0.1 if perf_mode == "low" else 0.01
            await asyncio.sleep(sleep_duration)
        except Exception as e:
            print(f"Error in stream_generator for {camera_path}: {e}", file=sys.stderr)
            # If the client disconnects, this loop will break.
            break


# --- API Endpoints ---


@app.get("/api/detected_cameras")
async def get_detected_cameras():
    """
    Stops all currently active cameras, then scans for all available 
    physical cameras and returns their properties.
    This is a live view of connected cameras, independent of the config.
    """
    # Stop all running cameras before re-detecting.
    print("--- CLOSING ALL CAMERAS FOR RE-DETECTION ---", file=sys.stderr)
    # Iterate over a copy of the items, as `close()` might modify the original dict
    for camera_path, camera in list(active_cameras.items()):
        print(f"Closing camera: {camera_path}", file=sys.stderr)
        camera.close()
    active_cameras.clear()
    print("--- ALL CAMERAS CLOSED ---", file=sys.stderr)

    try:
        detected_cams = detect_cameras()
        return detected_cams
    except Exception as e:
        # Log the error for debugging
        print(f"Error detecting cameras: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"An error occurred while detecting cameras: {e}")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    print(f"[WS] New connection attempt from {websocket.client}", file=sys.stderr)
    await manager.connect(websocket)
    print(f"[WS] Connection accepted. Active connections: {len(manager.active_connections)}", file=sys.stderr)
    try:
        while True:
            # Keep the connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        print(f"[WS] Client disconnected: {websocket.client}", file=sys.stderr)
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}", file=sys.stderr)
        manager.disconnect(websocket)


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "active_page": "index"})

@app.get("/grid", response_class=HTMLResponse)
async def grid_view(request: Request):
    return templates.TemplateResponse("grid.html", {"request": request, "active_page": "grid"})

@app.get("/sftp", response_class=HTMLResponse)
async def sftp_view(request: Request):
    return templates.TemplateResponse("sftp.html", {"request": request, "active_page": "sftp"})

@app.get("/editor", response_class=HTMLResponse)
async def editor_view(request: Request):
    return templates.TemplateResponse("editor.html", {"request": request, "active_page": "editor"})

@app.get("/api/config", response_class=PlainTextResponse)
async def get_config():
    config = load_config()
    if config is None:
        raise HTTPException(status_code=404, detail="Config not found")
    return yaml.dump(config, default_flow_style=False)

class SaveConfigRequest(BaseModel):
    config: str
    selected_cameras: dict | None = None

class PerformanceModeRequest(BaseModel):
    mode: str

@app.post("/api/performance_mode")
async def save_performance_mode(request: PerformanceModeRequest):
    global system_config
    try:
        if request.mode not in ["high", "low", "auto"]:
            raise HTTPException(status_code=400, detail="Invalid mode. Must be 'high', 'low', or 'auto'.")

        # Update global config immediately
        system_config["performance_mode"] = request.mode
        
        # Resolve the mode if auto
        if request.mode == "auto":
             # We need to re-import or existing function should be available?
             # detect_system_performance is in config_handler, but it's not imported.
             # Actually load_config handles resolution.
             # Let's just reload the config logic to be safe/consistent
             from config_handler import detect_system_performance
             resolved = detect_system_performance()
             system_config["_resolved_performance_mode"] = resolved
        else:
             system_config["_resolved_performance_mode"] = request.mode

        # Persist to disk
        # We need to load existing file, update one key, and save, 
        # to avoid overwriting other unrelated changes if system_config is stale?
        # But system_config is the main source of truth.
        save_config(system_config)

        print(f"Performance mode changed to: {request.mode} (Resolved: {system_config['_resolved_performance_mode']})", file=sys.stderr)

        return {"status": "success", "mode": request.mode, "resolved": system_config["_resolved_performance_mode"]}

    except Exception as e:
        print(f"Error saving performance mode: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config")
async def save_config_endpoint(request: SaveConfigRequest):
    global available_cameras
    try:
        config_data = yaml.safe_load(request.config)
        if config_data is None:
            config_data = {"cameras": {}}
            
        # 1. Save the manual edits first (to ensure we don't lose them if merging fails, though we are in memory)
        # Actually, we just want to merge into the object derived from the YAML string.
        


        # 2. Merge selected cameras
        if request.selected_cameras is not None:
            config_data = generate_default_config(config_data, request.selected_cameras)
        
        # Always save the config to ensure user edits are persisted
        save_config(config_data)

        available_cameras = config_data.get('cameras', {})
        return {"status": "success"}
    except yaml.YAMLError:
        raise HTTPException(status_code=400, detail="Invalid YAML format")

@app.get("/api/active_cameras")
async def get_active_cameras():
    return list(active_cameras.keys())

@app.get("/api/camera_info/{camera_path}")
async def get_camera_info(camera_path: str):
    if camera_path not in available_cameras:
        raise HTTPException(status_code=404, detail="Camera not found")

    cam_info = available_cameras[camera_path]
    
    # We still need to create the camera object if it's not active
    if camera_path not in active_cameras:
        if cam_info.get('type') == 'usb':
             active_cameras[camera_path] = USBCamera(path=cam_info['path'], friendly_name=cam_info['friendly_name'])
        elif cam_info.get('type') == 'pi':
            active_cameras[camera_path] = PiCamera(
                camera_id=cam_info['path'],
                friendly_name=cam_info['friendly_name'],
                max_width=cam_info.get('max_width'),
                max_height=cam_info.get('max_height')
            )
    
    camera = active_cameras.get(camera_path)

    return {
        "camera_path": camera_path,
        "friendly_name": cam_info.get('friendly_name'),
        "type": cam_info.get('type'),
        "has_autofocus": cam_info.get('has_autofocus', False),
        "has_autofocus": cam_info.get('has_autofocus', False),
        "autofocus_enabled": camera._autofocus_enabled if camera and isinstance(camera, PiCamera) else None,
        "iso": camera._iso if camera and isinstance(camera, PiCamera) else None,
        "manual_focus_value": camera._manual_focus_value if camera and isinstance(camera, PiCamera) else None,
        "current_lens_position": camera.get_lens_position() if camera and isinstance(camera, PiCamera) else None
    }

@app.get("/api/cameras")
async def get_cameras():
    return available_cameras

@app.get("/api/resolutions")
async def get_resolutions(camera_path: str):
    if camera_path not in available_cameras:
        raise HTTPException(status_code=404, detail="Camera not found")
    return available_cameras[camera_path].get('resolutions', [])

@app.get("/api/shutter_speed_range/{camera_path}")
async def get_shutter_speed_range(camera_path: str):
    if camera_path not in available_cameras:
        raise HTTPException(status_code=404, detail="Camera not found")
    return available_cameras[camera_path].get('shutter_speed_range', [0, 0])

@app.post("/api/capture")
@app.post("/api/capture")
async def capture_image(request: CaptureRequest):
    try:
        # Convert single CaptureRequest to PerCameraCaptureSettings
        single_cap_request = PerCameraCaptureSettings(
            camera_path=request.camera_path,
            resolution=request.resolution,
            shutter_speed=request.shutter_speed,
            iso=request.iso,
            autofocus=request.autofocus,
            manual_focus=request.manual_focus,
            subfolder=request.subfolder,
            prefix=request.prefix
        )
        
        # Wrap in CaptureAllRequest
        global_request = CaptureAllRequest(
            captures=[single_cap_request]
        )
        
        # Delegate to the centralized logic (which handles SFTP, metadata, etc.)
        captured_files = await perform_global_capture(global_request, source="WebUI_Single")
        
        if not captured_files:
             raise HTTPException(status_code=500, detail="Capture failed or no files produced.")
             
        # Return success with the first file (to maintain partial API compatibility if needed, 
        # though original returned status+message. We can return that.)
        # Original response format was typically implicitly successful 200 OK. 
        # But we should return JSON.
        
        # Helper to get relative path
        def get_rel_path(p):
            try:
                return str(pathlib.Path(p).relative_to(CAPTURE_DIR_BASE))
            except ValueError:
                return str(pathlib.Path(p).name)

        files_list = [get_rel_path(f) for f in captured_files]
        first_file = files_list[0] if files_list else None
        
        return JSONResponse({
            "status": "success", 
            "message": "Capture successful", 
            "files": files_list,
            "filename": first_file # Key required by script.js
        })

    except Exception as e:
        print(f"Error in /api/capture: {e}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail=str(e))

class SaveCameraSettingsRequest(BaseModel):
    camera_path: str
    resolution: str | None = None
    shutter_speed: str | None = None
    iso: int | None = None
    autofocus: bool | None = None
    prefix: str | None = None

@app.post("/api/save_camera_settings")
async def save_camera_settings(request: SaveCameraSettingsRequest):
    global available_cameras
    try:
        if request.camera_path not in available_cameras:
             raise HTTPException(status_code=404, detail="Camera not found")

        # Update the in-memory config
        cam_config = available_cameras[request.camera_path]
        if request.resolution:
            cam_config['resolution'] = request.resolution
        if request.shutter_speed:
            cam_config['shutter_speed'] = request.shutter_speed
        if request.iso is not None:
             cam_config['iso'] = request.iso
        if request.autofocus is not None:
             cam_config['autofocus_enabled'] = request.autofocus

        # Load full config from file to persist it properly
        full_config = load_config()
        if 'cameras' not in full_config:
            full_config['cameras'] = {}
        
        # Save Global Defaults (Prefix)
        if request.prefix:
            if 'defaults' not in full_config:
                full_config['defaults'] = {}
            full_config['defaults']['prefix'] = request.prefix

        if request.camera_path in full_config['cameras']:
             full_config['cameras'][request.camera_path].update({
                 'resolution': request.resolution,
                 'shutter_speed': request.shutter_speed,
                 'iso': request.iso,
                 'autofocus_enabled': request.autofocus
             })
             # Filter out None values to keep config clean
             full_config['cameras'][request.camera_path] = {k: v for k, v in full_config['cameras'][request.camera_path].items() if v is not None}
        
        save_config(full_config)
        
        # Update available_cameras global to match
        available_cameras = full_config.get('cameras', {})
        # Note: We don't have a global var for defaults currently, we'll load it on demand or add it to a global config obj
        
        print(f"Saved settings for {request.camera_path}: Res={request.resolution}, AF={request.autofocus}, Prefix={request.prefix}", file=sys.stderr)
        return JSONResponse({"status": "success", "message": "Settings saved."})
    except Exception as e:
         print(f"Error saving camera settings: {e}", file=sys.stderr)
         raise HTTPException(status_code=500, detail=str(e))

class SetActiveCameraRequest(BaseModel):
    camera_path: Optional[str] = None

@app.post("/api/set_active_camera")
async def set_active_camera(request: SetActiveCameraRequest):
    global active_camera_context
    active_camera_context = request.camera_path
    mode = "Single Camera: " + request.camera_path if request.camera_path else "Multi-Camera (All)"
    print(f"Active camera context updated to: {active_camera_context} ({mode})", file=sys.stderr)
    return JSONResponse({"status": "success", "message": f"Context set to {mode}"})

@app.post("/api/capture_all")
async def capture_all_images(request: CaptureAllRequest):
    captured_files = await perform_global_capture(request, source="WebUI")
    
    if captured_files is None:
        raise HTTPException(status_code=500, detail="Capture failed")
        
    return JSONResponse({
        "status": "success", 
        "message": f"Captured {len(captured_files)} images", 
        "files": [str(pathlib.Path(f).name) for f in captured_files]
    })

@app.get("/api/sftp_config")
async def get_sftp_config_endpoint():
    from sftp_handler import SFTP_CONFIG_PATH
    import json
    if not os.path.exists(SFTP_CONFIG_PATH):
        return JSONResponse({})
    
    try:
        with open(SFTP_CONFIG_PATH, 'r') as f:
            config = json.load(f)
            # Mask password
            if 'password' in config:
                config['password'] = "********"
            return config
    except Exception as e:
        print(f"Error loading SFTP config: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail="Error loading config")

# --- Interval Capture Logic ---
async def interval_capture_loop(request: CaptureAllRequest, interval: float, count: int = 0):
    global interval_capture_running
    print(f"Starting interval capture: Interval={interval}s, Count={count}", file=sys.stderr)
    
    current_count = 0
    try:
        while interval_capture_running:
            if count > 0 and current_count >= count:
                print("Interval capture reached target count.", file=sys.stderr)
                break
                
            start_time = time.time()
            
            # Execute Capture
            print(f"Interval Capture {current_count + 1}/{count if count > 0 else 'Inf'}", file=sys.stderr)
            await perform_global_capture(request, source="Interval")
            current_count += 1
            
            # Calculate sleep to maintain accurate interval
            elapsed = time.time() - start_time
            sleep_time = max(0.0, interval - elapsed)
            
            if not interval_capture_running:
                break
                
            await asyncio.sleep(sleep_time)
            
    except Exception as e:
        print(f"Error in interval capture loop: {e}", file=sys.stderr)
    finally:
        interval_capture_running = False
        print("Interval capture loop stopped.", file=sys.stderr)
        await manager.broadcast({"type": "interval_status", "status": "stopped"})

@app.post("/api/start_interval")
async def start_interval(request: StartIntervalRequest):
    global interval_capture_running, interval_task
    
    if interval_capture_running:
        return JSONResponse({"status": "error", "message": "Interval capture already running"}, status_code=400)
    
    interval_capture_running = True
    
    # Context-Aware Logic
    captures_list = []
    mode_msg = "Global"
    
    # Check if we are in a specific camera context
    if active_camera_context and active_camera_context in active_cameras:
         mode_msg = f"Single ({active_camera_context})"
         captures_list.append(PerCameraCaptureSettings(
             camera_path=active_camera_context,
             subfolder=request.subfolder,
             prefix=request.prefix
         ))

    # Create capture request
    capture_req = CaptureAllRequest(
        subfolder=request.subfolder,
        prefix=request.prefix,
        captures=captures_list if captures_list else None # None = All Cameras
    )

    print(f"Starting interval capture [{mode_msg}]: Interval={request.interval_seconds}s, Count={request.total_count}", file=sys.stderr)
    
    # Start the background task
    interval_task = asyncio.create_task(
        interval_capture_loop(capture_req, request.interval_seconds, request.total_count)
    )
    
    await manager.broadcast({"type": "interval_status", "status": "running", "params": request.dict()})
    return {"status": "success", "message": "Interval capture started"}

@app.post("/api/stop_interval")
async def stop_interval():
    global interval_capture_running
    if not interval_capture_running:
         return {"status": "ignored", "message": "Not running"}
         
    interval_capture_running = False
    # The loop will check this flag and exit
    return {"status": "success", "message": "Stopping interval capture..."}

@app.get("/api/interval_status")
async def get_interval_status():
    return {"status": "running" if interval_capture_running else "stopped"}

@app.post("/api/sftp_config")
async def save_sftp_config_endpoint(config: SFTPConfig):
    from sftp_handler import SFTP_CONFIG_PATH
    import json
    
    try:
        # Load existing to check for password update if it is masked
        existing_pass = None
        if os.path.exists(SFTP_CONFIG_PATH):
             with open(SFTP_CONFIG_PATH, 'r') as f:
                  load_c = json.load(f)
                  existing_pass = load_c.get('password')
        
        # Prepare data
        data = config.dict()
        
        # If password is mask ********, keep existing
        if data['password'] == "********" and existing_pass:
             data['password'] = existing_pass
             
        with open(SFTP_CONFIG_PATH, 'w') as f:
            json.dump(data, f, indent=4)
            
        print(f"SFTP Config saved. Enabled: {data['enabled']}", file=sys.stderr)
        return JSONResponse({"status": "success", "message": "SFTP Configuration saved"})
        
    except Exception as e:
        print(f"Error saving SFTP config: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))
        raise HTTPException(status_code=500, detail="No images were captured.")

    return JSONResponse({
        "status": "success",
        "message": f"Captured {len(captured_files)} images.",
        "captured_files": captured_files,
        "total_captures": capture_count
    })

@app.post("/api/autofocus")
async def set_autofocus(request: AutofocusRequest):
    try:
        camera_path = request.camera_path
        enable_autofocus = request.enable

        if camera_path not in active_cameras:
            raise HTTPException(status_code=404, detail="Camera not active or not found.")

        camera = active_cameras[camera_path]
        if isinstance(camera, PiCamera):
            camera.set_autofocus(enable_autofocus)
            return JSONResponse({"status": "success", "message": f"Autofocus set to {enable_autofocus} for {camera_path}"})
        else:
            raise HTTPException(status_code=400, detail="Autofocus control is only available for PiCamera.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/manual_focus")
async def set_manual_focus(request: ManualFocusRequest):
    try:
        camera_path = request.camera_path
        focus_value = request.focus_value

        if camera_path not in active_cameras:
            raise HTTPException(status_code=404, detail="Camera not active or not found.")

        camera = active_cameras[camera_path]
        if isinstance(camera, PiCamera):
            camera.set_manual_focus(focus_value)
            return JSONResponse({"status": "success", "message": f"Manual focus set to {focus_value} for {camera_path}"})
        else:
            raise HTTPException(status_code=400, detail="Manual focus control is only available for PiCamera.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CreateDirectoryRequest(BaseModel):
    parent_path: str
    new_folder_name: str

@app.get("/api/list_directories")
async def list_directories(path: str = ""):
    """Lists subdirectories within the capture directory."""
    try:
        # Sanitize and resolve path
        target_path = (CAPTURE_DIR_BASE / "images" / path).resolve()
        base_path = (CAPTURE_DIR_BASE / "images").resolve()

        # Security check: Ensure target_path is within base_path
        if not str(target_path).startswith(str(base_path)):
            raise HTTPException(status_code=403, detail="Access denied: Path outside capture directory.")

        if not target_path.exists():
            return []

        directories = []
        for item in target_path.iterdir():
            if item.is_dir():
                directories.append(item.name)
        
        return sorted(directories)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/captured_files")
async def list_captured_files():
    # ... logic for listing captured files ...
    files = []
    if os.path.exists(CAPTURE_DIR_BASE): # Assuming CAPTURE_DIR_BASE is the root for captures
        for root, dirs, filenames in os.walk(CAPTURE_DIR_BASE):
             for filename in filenames:
                # Make paths relative to CAPTURE_DIR_BASE for cleaner output
                relative_path = os.path.relpath(os.path.join(root, filename), CAPTURE_DIR_BASE)
                files.append(relative_path)
    return sorted(files)


class MQTTUpdateRequest(BaseModel):
    enabled: bool = True
    broker: str
    port: int | None = 1883
    topic: str
    username: str | None = None
    password: str | None = None

@app.get("/api/mqtt_config")
async def get_mqtt_config_api():
    config = load_mqtt_config()
    # Ensure enabled key exists for frontend
    if 'enabled' not in config:
        config['enabled'] = True
    return config

@app.post("/api/mqtt_config")
async def save_mqtt_config_api(request: MQTTUpdateRequest):
    try:
        config = request.model_dump()
        # Ensure port is set to default if None (Pydantic default might not apply if explicitly None is passed? 
        # Actually Pydantic v2 handles it, but let's be safe for v1/v2 compat)
        if config.get('port') is None:
             config['port'] = 1883
             
        save_mqtt_config(config)
        
        # Restart MQTT Client with new settings (Hot Reload)
        global mqtt_client
        if mqtt_client:
            print("Stopping existing MQTT client...", file=sys.stderr)
            mqtt_client.stop()
        
        # Reload config to get fresh values (and handle defaults)
        mqtt_config = load_mqtt_config()
        enabled = mqtt_config.get('enabled', True)
        
        if enabled:
            broker = mqtt_config.get('broker', 'localhost')
            port = mqtt_config.get('port', 1883)
            topic = mqtt_config.get('topic', 'capture/trigger')
            username = mqtt_config.get('username')
            password = mqtt_config.get('password')

            loop = asyncio.get_running_loop()
            mqtt_client = MQTTClientWrapper(broker, port, topic, mqtt_callback, loop, username, password, mqtt_log_callback)
            mqtt_client.start()
            print(f"MQTT Client restarted with new config: {broker}:{port}", file=sys.stderr)
        else:
            print("MQTT disabled. Client stopped.", file=sys.stderr)
            mqtt_client = None
        return JSONResponse({"status": "success", "message": "Configuration saved and connection restarted."})
        
    except Exception as e:
        print(f"Error restarting MQTT client: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mqtt/test")
async def test_mqtt_connection():
    if mqtt_client and mqtt_client.connected:
        return {
            "status": "connected", 
            "detail": f"Connected to {mqtt_client.broker}:{mqtt_client.port}"
        }
    else:
        return {
            "status": "disconnected", 
            "detail": "Client not connected"
        }

@app.get("/api/mqtt_status")
async def get_mqtt_status():
    if not mqtt_client:
        return {"connected": False, "broker": None}
    return {
        "connected": mqtt_client.connected,
        "broker": mqtt_client.broker,
        "topic": mqtt_client.topic
    }

@app.post("/api/create_directory")
async def create_directory(request: CreateDirectoryRequest):
    try:
        # Sanitize and resolve path
        target_path = (CAPTURE_DIR_BASE / "images" / request.parent_path).resolve()
        base_path = (CAPTURE_DIR_BASE / "images").resolve()

        # Security check
        if not str(target_path).startswith(str(base_path)):
            raise HTTPException(status_code=403, detail="Access denied: Path outside capture directory.")

        # Sanitize new folder name
        safe_name = "".join(c for c in request.new_folder_name if c.isalnum() or c in ('_', '-')).strip()
        if not safe_name:
            raise HTTPException(status_code=400, detail="Invalid folder name.")

        new_dir = target_path / safe_name
        if new_dir.exists():
             raise HTTPException(status_code=400, detail="Directory already exists.")
        
        new_dir.mkdir(parents=True)
        return JSONResponse({"status": "success", "message": f"Created directory: {safe_name}"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DeleteDirectoryRequest(BaseModel):
    path: str

@app.post("/api/delete_directory")
async def delete_directory(request: DeleteDirectoryRequest):
    try:
        # Sanitize and resolve path
        target_path = (CAPTURE_DIR_BASE / "images" / request.path).resolve()
        base_path = (CAPTURE_DIR_BASE / "images").resolve()

        # Security check
        if not str(target_path).startswith(str(base_path)):
            raise HTTPException(status_code=403, detail="Access denied: Path outside capture directory.")

        if not target_path.exists():
             raise HTTPException(status_code=404, detail="Directory not found.")
        
        if not target_path.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory.")

        # Recursive delete
        import shutil
        shutil.rmtree(target_path)
        
        return JSONResponse({"status": "success", "message": f"Deleted directory: {request.path}"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
        new_dir.mkdir(parents=True, exist_ok=True)
        return JSONResponse({"status": "success", "message": f"Created directory: {safe_name}"})

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class DeleteImagesRequest(BaseModel):
    filenames: list[str]

@app.post("/api/delete_images")
async def delete_images(request: DeleteImagesRequest):
    try:
        deleted_count = 0
        errors = []
        
        for filename in request.filenames:
            # Sanitize and resolve path (filenames are expected to be relative to CAPTURE_DIR_BASE)
            # e.g. "images/default/IMG_....jpg"
            target_path = (CAPTURE_DIR_BASE / filename).resolve()
            
            # Security check
            if not str(target_path).startswith(str(CAPTURE_DIR_BASE.resolve())):
                errors.append(f"Access denied: {filename}")
                continue
                
            if target_path.exists() and target_path.is_file():
                try:
                    target_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    errors.append(f"Failed to delete {filename}: {e}")
            else:
                errors.append(f"File not found: {filename}")
                
        if errors:
             return JSONResponse({"status": "partial_success", "deleted_count": deleted_count, "errors": errors}, status_code=207)

        return JSONResponse({"status": "success", "deleted_count": deleted_count})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system_stats")
async def api_system_stats():
    try:
        stats = get_system_stats()
        stats['performance_mode'] = system_config.get("_resolved_performance_mode", "high")
        stats['camera_count'] = len(available_cameras)
        return stats
    except Exception as e:
        print(f"Stats Error: {e}", file=sys.stderr)
        return {"error": str(e)}

@app.get("/video_feed")
async def video_feed(camera_path: str, resolution: str = "1280x720", shutter_speed: str = "Auto", iso: int = 0,
                     preview_quality: int = 70, preview_width: int = 1280):
    try:
        if camera_path not in available_cameras:
            raise HTTPException(status_code=404, detail="Camera not found")

        if camera_path not in active_cameras:
            cam_info = available_cameras[camera_path]
            if cam_info.get('type') == 'usb':
                active_cameras[camera_path] = USBCamera(path=cam_info['path'], friendly_name=cam_info['friendly_name'])
            elif cam_info.get('type') == 'pi':
                active_cameras[camera_path] = PiCamera(
                    camera_id=cam_info['path'],
                    friendly_name=cam_info['friendly_name'],
                    max_width=cam_info['max_width'],
                    max_height=cam_info['max_height']
                )
        
        camera = active_cameras[camera_path]
        # Ensure camera is started before streaming
        if not camera.is_running:
            camera.start()

        # Prepare resolution
        width, height = map(int, resolution.split('x'))
        
        # Store the user's intended resolution in the camera object
        # This allows MQTT/Global captures to use the "Real" resolution even if preview is capped
        camera.preferred_resolution = (width, height)
        
        # OOM FIX: Cap resolution for Low Performance Mode (Pi Zero 2W)
        perf_mode = system_config.get("_resolved_performance_mode", "high")
        if perf_mode == "low":
             SAFE_MAX_WIDTH = 1280
             SAFE_MAX_HEIGHT = 720
             if width > SAFE_MAX_WIDTH or height > SAFE_MAX_HEIGHT:
                 print(f"[{perf_mode}] High resolution requested ({width}x{height}). Capping to {SAFE_MAX_WIDTH}x{SAFE_MAX_HEIGHT} to prevent OOM.", file=sys.stderr)
                 width = SAFE_MAX_WIDTH
                 height = SAFE_MAX_HEIGHT

        camera.set_resolution(width, height)
        if isinstance(camera, PiCamera):
            shutter_speed_us = parse_shutter_speed(shutter_speed)
            camera.set_shutter_speed(shutter_speed_us)
            camera.set_iso(iso)

        return StreamingResponse(
            stream_generator(camera_path, quality=preview_quality, max_width=preview_width), 
            media_type="multipart/x-mixed-replace; boundary=frame"
        )

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid resolution format. Please use WxH (e.g., 1280x720).")
    except Exception as e:
        import traceback
        print(f"Error in video_feed endpoint: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))

# --- Main Execution ---
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)