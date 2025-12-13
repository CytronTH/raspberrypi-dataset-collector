
import sys
import os
import time
import json
import threading
import paho.mqtt.client as mqtt

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config_handler import load_mqtt_config
from main import load_config as load_camera_config

# Load MQTT Config
mqtt_config = load_mqtt_config()
BROKER = mqtt_config.get('broker', 'localhost')
PORT = mqtt_config.get('port', 1883)
TRIGGER_TOPIC = mqtt_config.get('topic', 'capture/trigger')
CONFIRMATION_TOPIC = "dataset_collector/capture/finished"

confirmation_event = threading.Event()
received_confirmation = {}

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code {rc}")
    client.subscribe(CONFIRMATION_TOPIC)

def on_message(client, userdata, msg):
    global received_confirmation
    print(f"Received message on {msg.topic}: {msg.payload.decode()}")
    received_confirmation = json.loads(msg.payload.decode())
    confirmation_event.set()

def test_persistent_config():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Load username/password if set
    if mqtt_config.get('username'):
        client.username_pw_set(mqtt_config['username'], mqtt_config.get('password'))

    print(f"Connecting to {BROKER}:{PORT}...")
    try:
        # 1. Set a specific resolution for pi_0 via API (Simulate "Save Settings")
        import urllib.request
        import urllib.error
        
        target_res = "1280x720"
        target_prefix = "CUSTOM_PREFIX"
        
        print(f"Saving settings for pi_0 with resolution {target_res} and prefix {target_prefix}...")
        save_payload = json.dumps({
            "camera_path": "pi_0",
            "resolution": target_res,
            "shutter_speed": "Auto",
            "autofocus": True,
            "prefix": target_prefix
        }).encode('utf-8')
        
        req = urllib.request.Request("http://localhost:8000/api/save_camera_settings", data=save_payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response:
            print(f"Save response: {response.read().decode()}")

        client.connect(BROKER, PORT, 60)
        client.loop_start()
        
        time.sleep(2)
        
        # 2. Trigger MQTT capture with EMPTY payload (should use saved config AND prefix)
        print(f"Publishing trigger to {TRIGGER_TOPIC} (Empty payload)...")
        client.publish(TRIGGER_TOPIC, "{}") 
        
        print("Waiting for confirmation...")
        if confirmation_event.wait(timeout=15):
            print("Confirmation received!")
            print(json.dumps(received_confirmation, indent=2))
            
            if received_confirmation.get("status") == "success":
                # Check if the captured file exists
                files = received_confirmation.get("files", [])
                if files:
                    filename = files[0] 
                    if target_prefix in filename:
                        print(f"TEST PASSED: Capture successful using persistent config and prefix ({filename}).")
                    else:
                        print(f"TEST FAILED: Filename {filename} does not contain expected prefix {target_prefix}")
                else:
                     print("TEST FAILED: No files returned.")
            else:
                print(f"TEST FAILED: Status is {received_confirmation.get('status')}")
        else:
            print("TEST FAILED: Timeout waiting for confirmation")

        client.loop_stop()
        client.disconnect()
        
    except Exception as e:
        print(f"Test failed with exception: {e}")

if __name__ == "__main__":
    test_persistent_config()
