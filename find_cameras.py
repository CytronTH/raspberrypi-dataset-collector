
import cv2

def find_cameras():
    index = 0
    arr = []
    while index < 10: # Check up to 10 indices
        cap = cv2.VideoCapture(index)
        if cap.isOpened():
            print(f"Camera found at index {index}")
            arr.append(index)
            cap.release()
        index += 1
    return arr

if __name__ == '__main__':
    camera_indices = find_cameras()
    if camera_indices:
        print(f"Available camera indices: {camera_indices}")
    else:
        print("No cameras found.")
