import time
import sys
from picamera2 import Picamera2

def test_config():
    print("Initializing Picamera2...")
    picam2 = Picamera2()
    
    # Target resolutions
    preview_res = (1280, 720)
    high_res = (4608, 2592) # Example high res

    print(f"Testing configuration with main={preview_res} and sensor={high_res}...")
    
    try:
        # Try the syntax I used
        config = picam2.create_video_configuration(
            main={"size": preview_res},
            sensor={"size": high_res}
        )
        print("Configuration created successfully!")
        print(f"Config: {config}")
        
        # Determine what sensor mode was actually selected
        # config is a dict-like object (or internal C++ obj wrapper)
        # We can try to print strict info if possible
        
    except Exception as e:
        print(f"FAILED to create configuration: {e}")
        import traceback
        traceback.print_exc()

    picam2.close()

if __name__ == "__main__":
    test_config()
