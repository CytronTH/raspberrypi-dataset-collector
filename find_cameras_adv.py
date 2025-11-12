
import os

def find_cameras_with_names():
    video_devices = []
    video_dir = '/sys/class/video4linux'
    if os.path.exists(video_dir):
        for device in sorted(os.listdir(video_dir)):
            if device.startswith('video'):
                index = int(device.replace('video', ''))
                name_file = os.path.join(video_dir, device, 'name')
                if os.path.exists(name_file):
                    with open(name_file, 'r') as f:
                        friendly_name = f.read().strip()
                    video_devices.append({"id": index, "friendly_name": friendly_name, "path": f"/dev/{device}"})
    return video_devices

if __name__ == '__main__':
    cameras = find_cameras_with_names()
    if cameras:
        print("Found the following cameras:")
        for camera in cameras:
            print(f"  ID: {camera['id']}, Friendly Name: {camera['friendly_name']}, Path: {camera['path']}")
    else:
        print("No cameras found. Make sure your cameras are connected properly.")
