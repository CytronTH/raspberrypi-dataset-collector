
import urllib.request
import json
import time
import sys

URL = "http://localhost:8000/api/system_stats"

def verify_camera_count():
    print("Verifying Camera Count in API...")
    try:
        req = urllib.request.Request(URL)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            print(f"System Stats: {json.dumps(data, indent=2)}")
            
            count = data.get("camera_count")
            if count is not None and isinstance(count, int):
                print(f"SUCCESS: camera_count detected: {count}")
            else:
                print(f"FAILURE: camera_count missing or invalid: {count}")
                sys.exit(1)
                
    except Exception as e:
        print(f"Error checking API: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Wait for server if needed
    time.sleep(2) 
    verify_camera_count()
