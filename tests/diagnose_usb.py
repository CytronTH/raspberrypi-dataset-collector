import cv2
import subprocess
import sys

def list_v4l2_devices():
    print("--- v4l2-ctl --list-devices ---")
    try:
        result = subprocess.run(['v4l2-ctl', '--list-devices'], capture_output=True, text=True)
        print(result.stdout)
        return result.stdout
    except Exception as e:
        print(f"Error running v4l2-ctl: {e}")
        return ""

def test_opencv_index(index):
    print(f"--- Testing cv2.VideoCapture({index}) ---")
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        print(f"Failed to open camera at index {index}")
        return False
    
    # Try to read a frame
    ret, frame = cap.read()
    if ret:
        print(f"Successfully captured frame at index {index}")
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        print(f"Resolution: {width}x{height}")
    else:
        print(f"Opened camera at index {index}, but failed to read frame.")
    
    cap.release()
    return ret

if __name__ == "__main__":
    output = list_v4l2_devices()
    
    # Parse output to find likely indices for "USB" or "FHD"
    indices_to_test = []
    
    # Always test 0, 1, 2
    indices_to_test.extend([0, 1, 2])
    
    # Look for /dev/videoN in output
    lines = output.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('/dev/video'):
            try:
                idx = int(line.replace('/dev/video', ''))
                if idx not in indices_to_test:
                    indices_to_test.append(idx)
            except ValueError:
                pass
                
    print(f"Indices to test: {indices_to_test}")
    
    for idx in indices_to_test:
        test_opencv_index(idx)
