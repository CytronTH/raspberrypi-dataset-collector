from camera_handler import detect_cameras
import sys

print("Testing detect_cameras()...")
cameras = detect_cameras()
print("\nDetected Cameras:")
for key, info in cameras.items():
    print(f"Key: {key}")
    print(f"  Name: {info['friendly_name']}")
    print(f"  Type: {info['type']}")
    print(f"  Path: {info['path']}")
    print("-" * 20)
