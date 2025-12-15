
import cv2
import time
import pathlib
import os
import glob
from picamera2 import Picamera2, Preview
from picamera2.encoders import H264Encoder, Quality
from picamera2.outputs import FileOutput
from libcamera import controls
from threading import Thread, Event
import sys
import traceback



class CameraBase:
    def __init__(self, path, friendly_name):
        self.path = path
        self.friendly_name = friendly_name
        self.thread = None
        self.frame = None
        self.is_running = False
        self.ready_event = Event()

    def start(self):
        self.is_running = True
        self.ready_event.clear()
        print(f"[CameraBase {self.path}] Starting capture thread.", file=sys.stderr)
        self.thread = Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join()

    def close(self):
        """Stops the camera and releases any resources."""
        self.stop()

    def get_frame(self):
        return self.frame

    def capture_still(self):
        """Signals the capture loop to capture a fresh frame and waits for it."""
        if not self.is_running or not self.picam2:
            return None

        # Forcefully re-apply the manual focus settings right before capture.
        # This is to combat any background process that might be changing the focus.
        print(f"[PiCamera] Forcing manual focus to {self._manual_focus_value} before capture.", file=sys.stderr)
        self.picam2.set_controls({
            "AfMode": controls.AfModeEnum.Manual, 
            "LensPosition": self._manual_focus_value
        })
        # Give it a tiny moment to apply.
        time.sleep(0.1)

        self.frame_captured.clear()
        self.capture_requested.set()
        
        # Wait for the background thread to capture the frame
        if self.frame_captured.wait(timeout=2.0): # 2-second timeout
            return self.captured_frame
        else:
            print("[PiCamera] Warning: Timed out waiting for still frame. Returning last streaming frame.", file=sys.stderr)
            return self.frame # Fallback to the streaming frame on timeout

    def autofocus_and_capture(self):
        if self.picam2 and self._has_autofocus:
            print("Starting autofocus cycle...", file=sys.stderr)
            if self.picam2.autofocus_cycle():
                print("Autofocus successful.", file=sys.stderr)
            else:
                print("Autofocus failed.", file=sys.stderr)
        return self.picam2.capture_array()

    def set_resolution(self, width, height):
        raise NotImplementedError()



    def set_shutter_speed(self, shutter_speed):
        raise NotImplementedError()

    def capture_to_file(self, filepath):
        """Captures a frame directly to a file."""
        raise NotImplementedError()


    def _capture_loop(self):
        raise NotImplementedError()

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.friendly_name}>"

class USBCamera(CameraBase):
    """Handler for USB webcams using OpenCV."""
    def __init__(self, path, friendly_name):
        super().__init__(path, friendly_name)
        self.cap = None
        self.width = 1280
        self.height = 720

    def set_resolution(self, width, height):
        # No need to change if resolution is the same and it's running
        if self.width == width and self.height == height and self.is_running:
            return

        self.width = width
        self.height = height

        print(f"[USBCamera {self.path}] Setting resolution to {width}x{height}", file=sys.stderr)

        if self.is_running:
            print(f"[USBCamera {self.path}] Camera is running, stopping it first.", file=sys.stderr)
            self.stop()
            # Give the OS and camera driver a moment to release the device
            time.sleep(0.5) 

        print(f"[USBCamera {self.path}] Starting camera.", file=sys.stderr)
        self.start()
        
        # Wait for the camera thread to signal that it's ready
        if not self.ready_event.wait(timeout=10):
            print(f"[USBCamera {self.path}] WARNING: Camera did not become ready after resolution change.", file=sys.stderr)

    def set_shutter_speed(self, shutter_speed):
        # Most USB cameras don't support programmatic shutter speed control via OpenCV
        pass

    def capture_to_file(self, filepath):
        """Captures current frame to file using OpenCV."""
        if self.frame is None:
            raise RuntimeError("No frame available from USB camera")
        success = cv2.imwrite(filepath, self.frame)
        if not success:
             raise RuntimeError(f"Failed to write image to {filepath}")
        return filepath

    def capture_array(self):
        """Returns the latest captured frame (BGR)."""
        return self.frame

    def _capture_loop(self):
        print(f"[USBCamera {self.path}] _capture_loop started for {self.width}x{self.height}.", file=sys.stderr)
        try:
            self.cap = cv2.VideoCapture(self.path)
            if not self.cap.isOpened():
                print(f"[USBCamera {self.path}] Error: Could not open camera.", file=sys.stderr)
                self.is_running = False
                return

            # Set pixel format to MJPG for high resolutions
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            self.cap.set(cv2.CAP_PROP_FOURCC, fourcc)

            # Set the resolution
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

            # Verify the resolution
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if actual_width != self.width or actual_height != self.height:
                print(f"[USBCamera {self.path}] WARNING: Failed to set resolution to {self.width}x{self.height}. Actual resolution is {actual_width}x{actual_height}", file=sys.stderr)
                # Update internal state to what the camera is actually using
                self.width = actual_width
                self.height = actual_height

            print(f"[USBCamera {self.path}] Camera started with resolution {self.width}x{self.height}.", file=sys.stderr)
            self.ready_event.set()

        except Exception as e:
            print(f"Error in USBCamera _capture_loop: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            self.is_running = False
            return

        while self.is_running:
            ret, frame = self.cap.read()
            if not ret:
                print(f"[USBCamera {self.path}] Failed to capture frame.", file=sys.stderr)
                time.sleep(0.1)
                continue
            self.frame = frame
            time.sleep(0.01)
        
        print(f"[USBCamera {self.path}] _capture_loop stopped.", file=sys.stderr)
        if self.cap:
            self.cap.release()



class PiCamera(CameraBase):
    """A simplified, non-threaded handler for the Raspberry Pi Camera Module."""
    def __init__(self, camera_id, friendly_name, max_width, max_height):
        super().__init__(path=f"pi_{camera_id}", friendly_name=friendly_name)
        self.camera_id = camera_id
        self.friendly_name = friendly_name
        self.picam2 = Picamera2(self.camera_id)
        self.width = 1280
        self.height = 720
        self.max_width = max_width
        self.max_height = max_height
        self._autofocus_enabled = True
        self._manual_focus_value = 0.0
        self._shutter_speed = 0
        self._has_autofocus = False
        self.is_running = False

    def start(self):
        if self.is_running:
            return
        config = self.picam2.create_video_configuration(main={"size": (self.width, self.height)})
        self.picam2.configure(config)
        self.picam2.start()
        self.picam2.set_overlay(None)
        self.is_running = True
        self._has_autofocus = "AfMode" in self.picam2.camera_controls
        # Apply initial control settings
        if self._has_autofocus:
            self.set_autofocus(self._autofocus_enabled)
        self.set_shutter_speed(self._shutter_speed)
        print(f"[PiCamera {self.camera_id}] Camera started.", file=sys.stderr)

    def stop(self):
        if not self.is_running:
            return
        print(f"[PiCamera {self.camera_id}] Stopping camera.", file=sys.stderr)
        self.picam2.stop()
        self.is_running = False

    def close(self):
        """Stops and closes the camera, releasing all resources."""
        print(f"[PiCamera {self.camera_id}] Closing camera.", file=sys.stderr)
        self.picam2.close()
        self.is_running = False

    def set_resolution(self, width, height):
        if self.width == width and self.height == height:
            return
        self.width = width
        self.height = height
        if self.is_running:
            self.stop()
            self.start()

    def set_shutter_speed(self, shutter_speed):
        self._shutter_speed = shutter_speed
        if self.is_running and "AeEnable" in self.picam2.camera_controls:
            if shutter_speed == 0:
                self.picam2.set_controls({"AeEnable": True})
            else:
                self.picam2.set_controls({"AeEnable": False, "ExposureTime": shutter_speed})

    def set_autofocus(self, enable: bool):
        self._autofocus_enabled = enable
        if self.is_running and self._has_autofocus:
            if enable:
                self.picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous})
            else:
                # Get the current lens position from the metadata
                metadata = self.picam2.capture_metadata()
                current_pos = metadata.get("LensPosition", 0.0)
                
                # Lock the focus at the current position
                self.picam2.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": current_pos})
                
                # Update our internal state to match
                self._manual_focus_value = current_pos
                print(f"[PiCamera] Autofocus OFF. Focus locked at {current_pos:.2f}", file=sys.stderr)

    def set_manual_focus(self, focus_value: float):
        self._autofocus_enabled = False
        self._manual_focus_value = focus_value
        if self.is_running and self._has_autofocus:
            self.picam2.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": focus_value})

    def capture_to_file(self, filepath):
        """Captures directly to file using Picamera2's efficient encoder."""
        if not self.is_running:
             raise RuntimeError("Camera not running")
        
        # We use capture_file which streams directly to disk via encoder
        # This avoids loading the raw array into Python memory
        self.picam2.capture_file(filepath)
        return filepath

    def capture_array(self):
        """Captures a single frame. Renamed from capture_still for clarity."""
        if not self.is_running:
            return None
        return self.picam2.capture_array()

    def autofocus_and_capture(self):
        if self.picam2 and self._has_autofocus:
            print("Starting autofocus cycle...", file=sys.stderr)
            self.picam2.autofocus_cycle()
        return self.capture_array()
def detect_usb_cameras():
    """Detects USB cameras by scanning /dev/v4l/by-id/."""
    usb_cameras = {}
    try:
        # Find all USB camera symlinks
        # We look for 'index0' which is typically the video capture node
        paths = glob.glob('/dev/v4l/by-id/usb-*-video-index0')
        
        for symlink_path in paths:
            try:
                # Resolve the symlink to get the real device path (e.g., /dev/video16)
                real_path = os.path.realpath(symlink_path)
                
                # Extract the index from the real path
                basename = os.path.basename(real_path) # video16
                if not basename.startswith('video'):
                    continue
                
                cam_index = int(basename.replace('video', ''))
                
                # Extract a friendly name from the symlink
                # Format is usually usb-Manufacturer_Model_Serial-video-index0
                name_part = os.path.basename(symlink_path)
                name_part = name_part.replace('usb-', '').replace('-video-index0', '')
                friendly_name = f"USB Camera {cam_index} ({name_part})"
                
                usb_cameras[f"usb_{cam_index}"] = {
                    "friendly_name": friendly_name,
                    "type": "usb",
                    "path": cam_index, # Use the V4L2 index for OpenCV
                    "max_width": 1920, # Default max, can be updated if we probe
                    "max_height": 1080,
                    "resolutions": ['640x480', '1280x720', '1920x1080'],
                    "has_autofocus": False
                }
            except Exception as e:
                print(f"Error processing USB camera path {symlink_path}: {e}", file=sys.stderr)
                
    except Exception as e:
        print(f"Error in detect_usb_cameras: {e}", file=sys.stderr)
        
    return usb_cameras

def detect_cameras():
    print("--- DETECTING CAMERAS ---", file=sys.stderr)
    cameras = {}
    
    # 1. Detect Pi Cameras using Picamera2
    try:
        print("Scanning for Pi Cameras...", file=sys.stderr)
        pi_cameras_info = Picamera2.global_camera_info()
        if pi_cameras_info:
            for info in pi_cameras_info:
                # Skip if it looks like a USB camera (Picamera2 might list them)
                if "usb" in info.get('Id', '').lower():
                    continue
                    
                cam_id = info['Num']
                cam_name = f"PiCamera {cam_id} ({info.get('Model', 'Unknown')})"
                max_width, max_height = info.get('PixelArraySize', (4608, 2592))
                
                resolutions = []
                has_autofocus = False
                
                temp_cam = None
                try:
                    # Create a temporary instance to get detailed capabilities
                    temp_cam = Picamera2(cam_id)
                    has_autofocus = "AfMode" in temp_cam.camera_controls
                    
                    # Get and parse resolutions
                    res_set = set()
                    for mode in temp_cam.sensor_modes:
                        size = mode.get('size')
                        if size:
                            res_set.add(f"{size[0]}x{size[1]}")
                    
                    # Sort resolutions by width, then height
                    resolutions = sorted(list(res_set), key=lambda r: tuple(map(int, r.split('x'))))
    
                except Exception as e:
                    print(f"Could not get detailed info for camera {cam_id}: {e}", file=sys.stderr)
                    # Provide some default/fallback values
                    resolutions = ['640x480', '1280x720', '1920x1080']
                finally:
                    if temp_cam:
                        temp_cam.close() # Ensure camera is released
    
                cameras[f"pi_{cam_id}"] = {
                    "friendly_name": cam_name, 
                    "type": "pi", 
                    "path": cam_id,
                    "max_width": max_width,
                    "max_height": max_height,
                    "resolutions": resolutions,
                    "has_autofocus": has_autofocus
                }
    except Exception as e:
        print(f"Error detecting Pi cameras: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

    # 2. Detect USB Cameras
    try:
        print("Scanning for USB Cameras...", file=sys.stderr)
        usb_cams = detect_usb_cameras()
        cameras.update(usb_cams)
    except Exception as e:
        print(f"Error detecting USB cameras: {e}", file=sys.stderr)

    print(f"Detected cameras: {cameras}", file=sys.stderr)
    return cameras
