import cv2
import sys

try:
    print("Testing cv2.VideoCapture(2)...")
    cap = cv2.VideoCapture(2)
    if not cap.isOpened():
        print("Failed to open camera with index 2.")
    else:
        print("Successfully opened camera with index 2.")
        ret, frame = cap.read()
        if ret:
            print(f"Captured frame of size {frame.shape}")
        else:
            print("Failed to read frame.")
        cap.release()
except Exception as e:
    print(f"Error: {e}")
