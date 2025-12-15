
import asyncio
import sys
import os
import time

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import active_cameras, PiCamera, USBCamera
# Mocking imports if necessary, but we want to run this in the actual environment if possible.
# Actually, since we need the FastAPI app context or at least the camera objects initialized, 
# it's better to just import the camera classes and simulate the loop if we can't run the full app.
# However, the user issue is specifically about the app crashing.

# Let's try to simulate the capture logic directly on a camera instance first, 
# as that's where the memory allocation happens.

def test_camera_capture_memory_usage():
    print("--- Starting Capture OOM Stress Test ---")
    
    # Initialize a PiCamera (or mock if on PC, but this is for Pi Zero)
    # We'll assume we are on the device.
    
    # We need to manually initialize a camera similar to how main.py does it.
    from camera_handler import detect_cameras, PiCamera
    
    cameras = detect_cameras()
    pi_cams = [c for c in cameras.values() if c['type'] == 'pi']
    
    if not pi_cams:
        print("No PiCameras detected. Skipping test.")
        return

    cam_info = pi_cams[0]
    camera_id = cam_info['path']
    print(f"Testing on Camera: {cam_info['friendly_name']}")
    
    # Create Camera Instance
    cam = PiCamera(camera_id, cam_info['friendly_name'], cam_info['max_width'], cam_info['max_height'])
    
    try:
        cam.start()
        time.sleep(2) # Warmup
        
        # Start at Low Res (720p) - simulates Preview Mode
        preview_res = (1280, 720)
        print(f"Setting preview resolution: {preview_res}")
        cam.set_resolution(*preview_res) 
        cam.start()
        time.sleep(2) # Warmup
        
        # Test Resolution: Max (e.g. 12MP)
        max_res = (cam_info['max_width'], cam_info['max_height'])
        print(f"Target Capture Resolution: {max_res}")
        
        output_dir = "tests/output"
        os.makedirs(output_dir, exist_ok=True)
        
        print("Starting capture loop (switch res per capture)...")
        for i in range(5):
            filename = os.path.join(output_dir, f"capture_test_{i}.jpg")
            start_time = time.time()
            
            # --- THE CRITICAL CALL ---
            # Pass explicit resolution to force transient switch to Still Mode
            cam.capture_to_file(filename, width=max_res[0], height=max_res[1])
            # -------------------------
            
            duration = time.time() - start_time
            file_size = os.path.getsize(filename) / (1024*1024)
            print(f"Capture {i+1}: Saved {filename} ({file_size:.2f} MB) in {duration:.2f}s")
            
            # Optional: Check memory usage here if psutil is available
            # import psutil
            # print(f"RAM: {psutil.virtual_memory().percent}%")
            
            time.sleep(1)
            
        print("Test Complete. No crashes encountered.")
        
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cam.close()
        # Clean up files
        # for f in os.listdir(output_dir):
        #     os.remove(os.path.join(output_dir, f))

if __name__ == "__main__":
    test_camera_capture_memory_usage()
