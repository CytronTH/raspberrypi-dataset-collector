from picamera2 import Picamera2
import sys

try:
    print("Checking Picamera2.global_camera_info()...")
    infos = Picamera2.global_camera_info()
    print(f"Found {len(infos)} cameras.")
    for i, info in enumerate(infos):
        print(f"Camera {i}: {info}")
except Exception as e:
    print(f"Error: {e}")
