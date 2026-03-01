
import requests
import time
import sys

BASE_URL = "http://localhost:8000"

try:
    # 1. Get Config
    print("Fetching config...")
    res = requests.get(f"{BASE_URL}/api/config")
    res.raise_for_status()
    config_yaml = res.text
    print(f"Current Config Length: {len(config_yaml)}")

    if "overlay_settings: true" not in config_yaml:
        print("Enabling overlay...")
        if "overlay_settings: false" in config_yaml:
            config_yaml = config_yaml.replace("overlay_settings: false", "overlay_settings: true")
        elif "overlay_settings:" in config_yaml: # Handle case where it might be something else?
             pass 
        else:
            config_yaml = "overlay_settings: true\n" + config_yaml
        
        # Save Config
        res = requests.post(f"{BASE_URL}/api/config", json={"config": config_yaml})
        res.raise_for_status()
        print("Config saved.")
    else:
        print("Overlay already enabled.")

    # 2. Trigger Capture
    print("Triggering capture...")
    res = requests.post(f"{BASE_URL}/api/capture_all", json={"subfolder": "verification", "prefix": "TEST_OVERLAY"})
    
    print(f"Capture Response Code: {res.status_code}")
    if res.status_code == 200:
        print(f"Capture Result: {res.json()}")
    else:
        print(f"Capture Failed: {res.text}")

except Exception as e:
    print(f"Error: {e}")
