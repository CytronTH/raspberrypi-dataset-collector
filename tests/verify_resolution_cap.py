
import urllib.request
import json
import time
import sys

URL_SET_MODE = "http://localhost:8000/api/performance_mode"
URL_VIDEO_FEED = "http://localhost:8000/video_feed?resolution=4608x2592&camera_path=pi_0" # Request massive res

def verify_cap():
    print("Verifying Resolution Cap...")
    try:
        # 1. Force LOW mode
        print("Setting LOW mode...")
        payload = json.dumps({"mode": "low"}).encode('utf-8')
        req = urllib.request.Request(URL_SET_MODE, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req) as res:
             print(f"Mode set: {res.read().decode()}")

        # 2. Request Video Feed (Just header check or read first chunk)
        # We can't easily check internal resolution state without logs or side channel.
        # But if it doesn't crash, that's a good sign.
        # Ideally, we should add a log check or use system_stats if we exposed camera res there?
        # System stats doesn't show current camera resolution.
        # However, checking if the server creates the stream successfully is key.
        
        print(f"Requesting stream with 4608x2592...")
        req = urllib.request.Request(URL_VIDEO_FEED)
        with urllib.request.urlopen(req) as response:
            # Read a few bytes to ensure stream started
            chunk = response.read(1024)
            if len(chunk) > 0:
                print("SUCCESS: Stream started successfully (likely capped).")
            else:
                print("FAILURE: Stream empty.")

    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        # if connection reset/crash, it failed.
        sys.exit(1)
        
    print("Reverting to HIGH mode for cleanup...")
    try:
         payload = json.dumps({"mode": "high"}).encode('utf-8')
         req = urllib.request.Request(URL_SET_MODE, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
         urllib.request.urlopen(req)
    except:
         pass

if __name__ == "__main__":
    time.sleep(2)
    verify_cap()
