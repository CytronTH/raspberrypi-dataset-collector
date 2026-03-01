
import requests
import time
import sys

BASE_URL = "http://localhost:8000"

try:
    # 1. Start Interval Capture
    print("Starting interval capture (3 captures, 2s interval)...")
    res = requests.post(f"{BASE_URL}/api/start_interval", json={
        "interval_seconds": 2, 
        "total_count": 3,
        "prefix": "VERIFY_INT",
        "subfolder": "verify_interval"
    })
    print(f"Start Result: {res.json()}")
    
    if res.status_code != 200:
        sys.exit(1)

    # 2. Monitor status
    for i in range(10):
        time.sleep(1)
        res = requests.get(f"{BASE_URL}/api/interval_status")
        status = res.json().get("status")
        print(f"[{i+1}s] Status: {status}")
        if status == "stopped":
            break
            
    print("Interval capture finished or timed out.")

except Exception as e:
    print(f"Error: {e}")
