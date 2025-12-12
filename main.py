import cv2
import asyncio
import os
import time
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
import sys  # Import sys
from typing import Optional

# Import camera handling logic
from camera_handler import detect_cameras, USBCamera, PiCamera
from config_handler import (
    load_config, generate_default_config, save_config, 
    load_mqtt_config, save_mqtt_config
)
from mqtt_handler import MQTTClientWrapper

# --- Constants ---
# Define a safe base directory for all captures
CAPTURE_DIR_BASE = pathlib.Path("/home/pi/dataset_collector/captures")

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
            
            request = CaptureAllRequest(
                captures=[single_cap_request],
                prefix=data.get('prefix', 'IMG')
            )
    else:
        # Global context (Multi-cam) or invalid context
        print(f"[{'MQTT'}] Global context. Capturing all.", file=sys.stderr)
        request = CaptureAllRequest(**data)

    print(f"Triggering capture via MQTT with data: {original_data} -> Context: {active_camera_context}", file=sys.stderr)
    try:
        await perform_global_capture(request, source="MQTT")
    except Exception as e:
        print(f"Error executing MQTT capture: {e}", file=sys.stderr)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    """
    # --- Startup ---
    global available_cameras
    print("--- DETECTING CAMERAS ---")
    try:
        config = load_config()
        detected_cams = detect_cameras()
        config = generate_default_config(config, detected_cams)
        available_cameras = config.get('cameras', {})
        print(f"Detected cameras: {available_cameras}")
    except Exception as e:
        print(f"Error during camera detection: {e}", file=sys.stderr)


    # --- MQTT Client Implementation ---
    global mqtt_client
    try:
        mqtt_config = load_mqtt_config()
        broker = mqtt_config.get('broker', 'localhost')
        port = mqtt_config.get('port', 1883)
        topic = mqtt_config.get('topic', 'capture/trigger')
        username = mqtt_config.get('username')
        password = mqtt_config.get('password')
    except Exception as e:
        print(f"Error loading MQTT config: {e}", file=sys.stderr)
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
    mqtt_client = MQTTClientWrapper(broker, port, topic, mqtt_callback, loop, username, password, mqtt_log_callback)
    mqtt_client.start()
    
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
mqtt_client = None

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
    autofocus: bool | None = None
    manual_focus: float | None = None
    subfolder: str | None = None

class CaptureAllRequest(BaseModel):
    subfolder: str | None = "default"
    prefix: str | None = "IMG"
    resolution: str | None = None
    shutter_speed: str | None = None
    captures: list[PerCameraCaptureSettings] | None = None


# --- Static Files and Templates ---
# --- Static Files and Templates ---
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
    if not active_cameras:
        print(f"[{source}] No active cameras to capture from.", file=sys.stderr)
        return None

    capture_requests = request.captures or [
        PerCameraCaptureSettings(camera_path=cam_path, resolution=request.resolution, shutter_speed=request.shutter_speed)
        for cam_path in active_cameras.keys()
    ]

    original_settings = {}
    captured_files = []
    global capture_count

    try:
        # 1. Apply settings to all cameras first
        print(f"[{source}] Starting capture sequence for cameras: {[r.camera_path for r in capture_requests]}", file=sys.stderr)
        print(f"[{source}] Applying settings to all cameras...", file=sys.stderr)
        for capture_req in capture_requests:
            camera_path = capture_req.camera_path
            if camera_path not in active_cameras:
                continue
            
            camera = active_cameras[camera_path]
            original_settings[camera_path] = {
                "resolution": (camera.width, camera.height),
                "shutter_speed": getattr(camera, '_shutter_speed', None),
                "autofocus_enabled": getattr(camera, '_autofocus_enabled', None)
            }

            if capture_req.resolution:
                width, height = map(int, capture_req.resolution.split('x'))
                camera.set_resolution(width, height)

            if isinstance(camera, PiCamera):
                if capture_req.autofocus:
                    camera.set_autofocus(True)
                elif capture_req.autofocus is False:
                    camera.set_autofocus(False)
                
                if capture_req.shutter_speed:
                    camera.set_shutter_speed(parse_shutter_speed(capture_req.shutter_speed))

        # 2. Capture frames from all cameras (as simultaneously as possible)
        print(f"[{source}] Capturing frames from all cameras...", file=sys.stderr)
        frames = {}
        capture_time = int(time.time() * 1000)
        for capture_req in capture_requests:
            camera_path = capture_req.camera_path
            camera = active_cameras.get(camera_path)
            if not camera:
                continue

            frame = None
            if isinstance(camera, PiCamera):
                if capture_req.autofocus:
                    frame = camera.autofocus_and_capture()
                else:
                    frame = camera.capture_array()
            else:
                frame = camera.get_frame()
            
            if frame is not None:
                frames[camera_path] = frame
            else:
                print(f"Failed to get frame from {camera_path}", file=sys.stderr)

        # 3. Save all captured frames
        print(f"[{source}] Saving {len(frames)} captured frames...", file=sys.stderr)
        for capture_req in capture_requests: # Iterate through capture_requests to get per-camera settings
            camera_path = capture_req.camera_path
            print(f"[{source}] Processing frame for {camera_path}...", file=sys.stderr)
            frame = frames.get(camera_path)
            if frame is None:
                continue

            # Determine the subfolder for this specific camera
            current_subfolder = capture_req.subfolder or request.subfolder # Use per-camera subfolder, or global
            safe_current_subfolder_name = pathlib.Path(current_subfolder).name or "default"
            current_save_dir = CAPTURE_DIR_BASE / "images" / safe_current_subfolder_name
            current_save_dir.mkdir(parents=True, exist_ok=True) # Ensure directory exists

            if isinstance(active_cameras[camera_path], PiCamera):
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            safe_prefix = "".join(c for c in request.prefix if c.isalnum() or c in ('_', '-')).strip() or "IMG"
            filename = f"{safe_prefix}_{camera_path.replace('/', '_')}_{capture_time}.jpg"
            save_path = current_save_dir / filename # Use current_save_dir

            if cv2.imwrite(str(save_path), frame):
                print(f"[{source}] Saved image for {camera_path}: {save_path}", file=sys.stderr)
                captured_files.append(str(save_path))
                capture_count += 1
                # Add metadata if applicable
                if isinstance(active_cameras[camera_path], PiCamera):
                    metadata = active_cameras[camera_path].picam2.capture_metadata()
                    exposure_time_us = metadata.get('ExposureTime')
                    if exposure_time_us and exposure_time_us > 0:
                        exif_dict = {"Exif": {piexif.ExifIFD.ExposureTime: (exposure_time_us, 1_000_000)}}
                        piexif.insert(piexif.dump(exif_dict), str(save_path))
                
                # Broadcast new file event
                relative_filename = str(save_path.relative_to(CAPTURE_DIR_BASE))
                await manager.broadcast({
                    "type": "new_file",
                    "filename": relative_filename,
                    "camera_path": camera_path,
                    "source": source
                })
            else:
                print(f"[{source}] ERROR: Failed to save image from camera {camera_path}", file=sys.stderr)

        print(f"[{source}] Capture sequence complete. Total files saved: {len(captured_files)}", file=sys.stderr)

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

    return captured_files

# --- Video Streaming Generator ---
async def stream_generator(camera_path: str):
    camera = active_cameras.get(camera_path)
    if not camera or not camera.is_running:
        print("Camera not active for streaming", file=sys.stderr)
        return

    while True:
        try:
            frame_rgb = camera.capture_array()
            if frame_rgb is None:
                await asyncio.sleep(0.01)
                continue

            if isinstance(camera, PiCamera):
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                flag, encoded_image = cv2.imencode(".jpg", frame_bgr)
            else: # USBCamera
                flag, encoded_image = cv2.imencode(".jpg", frame_rgb)

            if not flag:
                continue

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encoded_image) + b'\r\n')
            
            await asyncio.sleep(0.01)
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

@app.get("/editor", response_class=HTMLResponse)
async def editor(request: Request):
    return templates.TemplateResponse("editor.html", {"request": request, "active_page": "editor"})

@app.get("/api/config", response_class=PlainTextResponse)
async def get_config():
    config = load_config()
    if config is None:
        raise HTTPException(status_code=404, detail="Config not found")
    return yaml.dump(config, default_flow_style=False)

class SaveConfigRequest(BaseModel):
    config: str
    selected_cameras: dict = {}

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
        if request.selected_cameras:
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
        "autofocus_enabled": camera._autofocus_enabled if camera and isinstance(camera, PiCamera) else None,
        "manual_focus_value": camera._manual_focus_value if camera and isinstance(camera, PiCamera) else None
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
async def capture_image(request: CaptureRequest):
    try:
        # Create a single-camera capture request locally
        # to reuse the global capture logic
        capture_req = CaptureAllRequest(
            subfolder=request.subfolder,
            prefix=request.prefix,
            captures=[
                PerCameraCaptureSettings(
                    camera_path=request.camera_path,
                    resolution=request.resolution,
                    shutter_speed=request.shutter_speed,
                    autofocus=request.autofocus,
                    manual_focus=request.manual_focus
                )
            ]
        )
        
        # Use "WebUI" as source for logging
        captured_files = await perform_global_capture(capture_req, source="WebUI")
        
        if not captured_files:
            raise HTTPException(status_code=500, detail="Capture failed: No file produced.")
            
        # Since we asked for one camera, we expect one file
        filename = captured_files[0]
        relative_path = pathlib.Path(filename).relative_to(CAPTURE_DIR_BASE)

        # Return the response format expected by script.js
        # (perform_global_capture already handled saving, metadata, and WS broadcast)
        return JSONResponse({
            "status": "success", 
            "message": f"Image saved to {filename}", 
            "capture_count": capture_count, 
            "filename": str(relative_path)
        })

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in capture_image: {e}", file=sys.stderr)
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
         raise HTTPException(status_code=404, detail="No active cameras to capture from.")

    if not captured_files:
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
    broker: str
    port: int
    topic: str
    username: str | None = None
    password: str | None = None

@app.get("/api/mqtt_config")
async def get_mqtt_config_api():
    return load_mqtt_config()

@app.post("/api/mqtt_config")
async def save_mqtt_config_api(request: MQTTUpdateRequest):
    try:
        config = request.model_dump()
        save_mqtt_config(config)
        
        # Restart MQTT Client with new settings (Hot Reload)
        global mqtt_client
        if mqtt_client:
            print("Stopping existing MQTT client...", file=sys.stderr)
            mqtt_client.stop()
        
        # Reload config to get fresh values (and handle defaults)
        mqtt_config = load_mqtt_config()
        broker = mqtt_config.get('broker', 'localhost')
        port = mqtt_config.get('port', 1883)
        topic = mqtt_config.get('topic', 'capture/trigger')
        username = mqtt_config.get('username')
        password = mqtt_config.get('password')

        loop = asyncio.get_running_loop()
        mqtt_client = MQTTClientWrapper(broker, port, topic, mqtt_callback, loop, username, password, mqtt_log_callback)
        mqtt_client.start()
        print(f"MQTT Client restarted with new config: {broker}:{port}", file=sys.stderr)
        
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

@app.get("/video_feed")
async def video_feed(camera_path: str, resolution: str = "1280x720", shutter_speed: str = "Auto"):
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

        width, height = map(int, resolution.split('x'))
        camera.set_resolution(width, height)
        if isinstance(camera, PiCamera):
            shutter_speed_us = parse_shutter_speed(shutter_speed)
            camera.set_shutter_speed(shutter_speed_us)

        return StreamingResponse(stream_generator(camera_path), media_type="multipart/x-mixed-replace; boundary=frame")

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid resolution format. Please use WxH (e.g., 1280x720).")
    except Exception as e:
        import traceback
        print(f"Error in video_feed endpoint: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))

# --- Main Execution ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)