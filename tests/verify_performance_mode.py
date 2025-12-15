
import urllib.request
import json
import time
import sys

URL = "http://localhost:8000/api/system_stats"
POST_URL = "http://localhost:8000/api/performance_mode"

def verify():
    print("Verifying Performance Mode API...")
    try:
        # 1. Check Initial State
        req = urllib.request.Request(URL)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            print(f"Initial Stats: {json.dumps(data, indent=2)}")
            
        # 2. Test Toggle to LOW
        print("\nTesting Mode Switch to LOW...")
        payload = json.dumps({"mode": "low"}).encode('utf-8')
        req = urllib.request.Request(POST_URL, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
        
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode())
            print(f"Switch Result: {res_data}")
            if res_data.get("resolved") == "low":
                 print("SUCCESS: Switched to LOW.")
            else:
                 print("FAILURE: Switch to LOW failed.")
                 sys.exit(1)

        # 3. Test Toggle to HIGH
        print("\nTesting Mode Switch to HIGH...")
        payload = json.dumps({"mode": "high"}).encode('utf-8')
        req = urllib.request.Request(POST_URL, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
        
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode())
            print(f"Switch Result: {res_data}")
            if res_data.get("resolved") == "high":
                 print("SUCCESS: Switched to HIGH.")
            else:
                 print("FAILURE: Switch to HIGH failed.")
                 sys.exit(1)

    except Exception as e:
        print(f"Error checking API: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Wait for server if needed
    time.sleep(2) 
    verify()
