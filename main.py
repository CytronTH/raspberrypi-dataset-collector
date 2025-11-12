import cv2
import asyncio
import os
import time
import pathlib
import yaml
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Body, Query
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import piexif # Import piexif
import sys # Import sys

# Import camera handling logic
from camera_handler import detect_cameras, USBCamera, PiCamera
from config_handler import (
    load_config, generate_default_config, save_config
)

# --- Constants ---
# Define a safe base directory for all captures
CAPTURE_DIR_BASE = pathlib.Path("/home/pi/dataset_collector/captures")

from contextlib import asynccontextmanager

# --- App Lifespan Management ---
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
    
    yield
    
    # --- Shutdown ---
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
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Helper Functions ---
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


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/grid", response_class=HTMLResponse)
async def grid_view(request: Request):
    return templates.TemplateResponse("grid.html", {"request": request})

@app.get("/editor", response_class=HTMLResponse)
async def editor(request: Request):
    return templates.TemplateResponse("editor.html", {"request": request})

@app.get("/api/config", response_class=PlainTextResponse)
async def get_config():
    config = load_config()
    if config is None:
        raise HTTPException(status_code=404, detail="Config not found")
    return yaml.dump(config, default_flow_style=False)

@app.post("/api/config")
async def save_config_endpoint(config: str = Body(...)):
    global available_cameras
    try:
        config_data = yaml.safe_load(config)
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
        camera_path = request.camera_path
        subfolder = request.subfolder or "default"
        resolution = request.resolution
        shutter_speed_str = request.shutter_speed

        if camera_path not in active_cameras:
            raise HTTPException(status_code=404, detail="Camera not active or not found.")

        camera = active_cameras[camera_path]
        if resolution:
            width, height = map(int, resolution.split('x'))
            camera.set_resolution(width, height)

        # --- Security Check ---
        # Clean the subfolder name to prevent directory traversal
        # This removes any "..", "/", or "\" from the name
        safe_subfolder_name = pathlib.Path(subfolder).name
        if not safe_subfolder_name:
            safe_subfolder_name = "default"

        save_dir = CAPTURE_DIR_BASE / "images" / safe_subfolder_name
        
        # Create the directory if it doesn't exist
        try:
            save_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not create directory: {e}")

        if isinstance(camera, PiCamera):
            if request.autofocus:
                frame = camera.autofocus_and_capture()
            else:
                frame = camera.capture_array()
        else:
            frame = camera.get_frame()
        if frame is None:
            raise HTTPException(status_code=500, detail="Could not get frame from camera.")

        if isinstance(camera, PiCamera):
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # Sanitize prefix
        prefix = request.prefix or "IMG"
        safe_prefix = "".join(c for c in prefix if c.isalnum() or c in ('_', '-')).strip()
        if not safe_prefix:
            safe_prefix = "IMG"

        filename = f"{safe_prefix}_{int(time.time() * 1000)}.jpg"
        save_path = save_dir / filename

        try:
            success = cv2.imwrite(str(save_path), frame)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to save image.")
            
            # Add exposure time to metadata for PiCamera
            if isinstance(camera, PiCamera):
                metadata = camera.picam2.capture_metadata()
                exposure_time_us = metadata.get('ExposureTime')
                
                if exposure_time_us is not None and exposure_time_us > 0:
                    # Convert microseconds to seconds for EXIF (rational number)
                    # Exif.ExposureTime is stored as a rational number (numerator/denominator)
                    # We'll use 1,000,000 as the denominator for microseconds to seconds
                    exposure_time_s_num = exposure_time_us
                    exposure_time_s_den = 1_000_000

                    exif_dict = {"Exif": {piexif.ExifIFD.ExposureTime: (exposure_time_s_num, exposure_time_s_den)}}
                    exif_bytes = piexif.dump(exif_dict)
                    piexif.insert(exif_bytes, str(save_path))

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error saving image or adding metadata: {e}")

        global capture_count
        capture_count += 1

        return JSONResponse({"status": "success", "message": f"Image saved to {save_path}", "capture_count": capture_count})
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid resolution format. Please use format WxH (e.g., 1280x720).")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/capture_all")
async def capture_all_images(request: CaptureAllRequest):
    if not active_cameras:
        raise HTTPException(status_code=404, detail="No active cameras to capture from.")

    capture_requests = request.captures or [
        PerCameraCaptureSettings(camera_path=cam_path, resolution=request.resolution, shutter_speed=request.shutter_speed)
        for cam_path in active_cameras.keys()
    ]

    original_settings = {}
    captured_files = []
    global capture_count

    try:
        # 1. Apply settings to all cameras first
        print("[INFO] Applying settings to all cameras...", file=sys.stderr)
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
        print("[INFO] Capturing frames from all cameras...", file=sys.stderr)
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
        print("[INFO] Saving captured frames...", file=sys.stderr)
        for capture_req in capture_requests: # Iterate through capture_requests to get per-camera settings
            camera_path = capture_req.camera_path
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
                captured_files.append(str(save_path))
                capture_count += 1
                # Add metadata if applicable
                if isinstance(active_cameras[camera_path], PiCamera):
                    metadata = active_cameras[camera_path].picam2.capture_metadata()
                    exposure_time_us = metadata.get('ExposureTime')
                    if exposure_time_us and exposure_time_us > 0:
                        exif_dict = {"Exif": {piexif.ExifIFD.ExposureTime: (exposure_time_us, 1_000_000)}}
                        piexif.insert(piexif.dump(exif_dict), str(save_path))
            else:
                print(f"Failed to save image from camera {camera_path}", file=sys.stderr)

    finally:
        # 4. Revert all settings
        print("[INFO] Reverting all camera settings...", file=sys.stderr)
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