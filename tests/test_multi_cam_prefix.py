
import sys
import os
import time
import json
import urllib.request
import urllib.error

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

API_URL = "http://localhost:8000/api/capture_all"

def test_multi_cam_prefix():
    print("Testing Multi-Camera Per-Camera Prefix...")

    # Define the payload mimicking the WebUI request from grid.js
    payload = {
        "prefix": "GLOBAL_DEF", # Global default
        "captures": [
            {
                "camera_path": "pi_0", 
                "resolution": "1280x720",
                "shutter_speed": "Auto",
                "autofocus": True,
                "prefix": "CAM_A" # Should override GLOBAL_DEF
            },
            {
                "camera_path": "pi_1",
                "resolution": "1280x720",
                "shutter_speed": "Auto", 
                "autofocus": True,
                "prefix": "" # Should fallback to GLOBAL_DEF (empty string handling)
            }
        ]
    }
    
    try:
        req = urllib.request.Request(API_URL, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            print(f"Response: {json.dumps(result, indent=2)}")
            
            if result.get("status") == "success":
                # Check filenames in the message or we might need to list files?
                # The response message usually says "Images saved to ..." or similar summary.
                # Actually perform_global_capture returns list of files but the API wrapper returns a summary message.
                # Let's check the API response format in main.py:
                # return JSONResponse({"status": "success", "message": f"Captured {len(captured_files)} images.", "files": ...})
                # Wait, I need to check if I updated the return of /api/capture_all to include files.
                # Looking at main.py (from memory/view), it returns standard success message.
                
                # Let's inspect specific files produced.
                # We can use /api/captures to list recent files and check names.
                # Or just rely on the test script to check the directory if running locally.
                pass
            else:
                print("Capture failed.")
                sys.exit(1)

        # Verify files
        time.sleep(1) # Allow FS to sync
        
        # Check recent captures via API
        with urllib.request.urlopen("http://localhost:8000/api/captures") as response:
            recent_files = json.loads(response.read().decode())
            print("Recent files:", recent_files[:5])
            
            # Expecting one file starting with CAM_A and one with GLOBAL_DEF (since pi_1 sent empty string)
            found_cam_a = False
            found_global = False
            
            for f in recent_files[:5]: # just check top few
                if "CAM_A_pi_0" in f:
                    found_cam_a = True
                if "GLOBAL_DEF_pi_1" in f:
                    found_global = True
            
            if found_cam_a and found_global:
                 print("TEST PASSED: Found both file patterns (CAM_A check and Fallback check).")
            else:
                 print(f"TEST FAILED: Missing patterns. CAM_A found: {found_cam_a}, GLOBAL found: {found_global}")
                 sys.exit(1)

    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_multi_cam_prefix()
