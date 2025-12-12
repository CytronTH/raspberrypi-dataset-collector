from camera_handler import USBCamera
import time
import cv2
import sys

# Use the known correct index
USB_INDEX = 16

print(f"Testing USBCamera with index {USB_INDEX}...")
cam = USBCamera(path=USB_INDEX, friendly_name="Test USB Cam")

try:
    print("Starting camera...")
    cam.start()
    
    # Wait for camera to be ready
    if not cam.ready_event.wait(timeout=5):
        print("Camera failed to become ready.")
        sys.exit(1)
        
    print("Camera ready. Testing capture_array()...")
    
    # Allow some frames to be captured
    time.sleep(1)
    
    frame = cam.capture_array()
    
    if frame is not None:
        print(f"Successfully captured frame. Shape: {frame.shape}")
        # Verify it's a valid image
        if frame.size > 0:
            print("Frame is valid.")
        else:
            print("Frame is empty.")
    else:
        print("capture_array() returned None.")

except Exception as e:
    print(f"Error: {e}")
finally:
    print("Stopping camera...")
    cam.stop()
    cam.close()
