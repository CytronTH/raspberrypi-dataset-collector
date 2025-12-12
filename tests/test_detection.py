from camera_handler import detect_cameras
import sys

print("Testing detect_cameras()...")
cameras = detect_cameras()
print(f"Detected {len(cameras)} cameras.")

usb_found = False
pi_found = False

for key, cam in cameras.items():
    print(f"Key: {key}, Type: {cam['type']}, Name: {cam['friendly_name']}")
    if cam['type'] == 'usb':
        usb_found = True
    if cam['type'] == 'pi':
        pi_found = True

if usb_found:
    print("SUCCESS: USB camera detected correctly.")
else:
    print("FAILURE: USB camera NOT detected as type 'usb'.")

if pi_found:
    print("SUCCESS: Pi camera detected correctly.")
else:
    print("FAILURE: Pi camera NOT detected as type 'pi'.")
