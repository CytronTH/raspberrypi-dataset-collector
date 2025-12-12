import requests
import json

url = "http://localhost:8000/api/config"
payload = {
    "config": "cameras: {}",
    "selected_cameras": {
        "usb_2": {
            "path": 2,
            "friendly_name": "Test USB Camera",
            "type": "usb",
            "resolutions": ["640x480"],
            "has_autofocus": False
        }
    }
}

try:
    print(f"Sending POST request to {url}...")
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
