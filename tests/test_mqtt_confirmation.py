import paho.mqtt.client as mqtt
import time
import json
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import threading
from config_handler import load_config, load_mqtt_config

# Load config to get broker details
mqtt_config = load_mqtt_config()
BROKER = mqtt_config.get('broker', 'localhost')
PORT = mqtt_config.get('port', 1883)
TRIGGER_TOPIC = mqtt_config.get('topic', 'capture/trigger')
USERNAME = mqtt_config.get('username')
PASSWORD = mqtt_config.get('password')

CONFIRMATION_TOPIC = "dataset_collector/capture/finished"

received_confirmation = None
confirmation_event = threading.Event()

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("Connected to MQTT Broker")
        client.subscribe(CONFIRMATION_TOPIC)
        print(f"Subscribed to {CONFIRMATION_TOPIC}")
    else:
        print(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    global received_confirmation
    print(f"Received message on {msg.topic}: {msg.payload.decode()}")
    try:
        received_confirmation = json.loads(msg.payload.decode())
        confirmation_event.set()
    except json.JSONDecodeError:
        print("Failed to decode JSON confirmation")

def test_confirmation():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    if USERNAME and PASSWORD:
        client.username_pw_set(USERNAME, PASSWORD)

    print(f"Connecting to {BROKER}:{PORT}...")
    try:
        # Activate camera first
        import urllib.request
        try:
            print("Activating camera pi_0 via API...")
            with urllib.request.urlopen("http://localhost:8000/api/camera_info/pi_1") as response:
                print(f"Camera activation info: {response.read().decode()}")
        except Exception as e:
            print(f"Warning: Failed to activate camera via API: {e}")

        client.connect(BROKER, PORT, 60)
        client.loop_start()
        
        # Wait for connection to settle
        time.sleep(2)
        
        print(f"Publishing trigger to {TRIGGER_TOPIC}...")
        client.publish(TRIGGER_TOPIC, json.dumps({"prefix": "TEST_CONFIRMATION"}))
        
        print("Waiting for confirmation...")
        if confirmation_event.wait(timeout=10):
            print("Confirmation received!")
            print(json.dumps(received_confirmation, indent=2))
            
            if received_confirmation.get("status") == "success":
                print("TEST PASSED: Status is success")
            else:
                print(f"TEST FAILED: Status is {received_confirmation.get('status')}")
        else:
            print("TEST FAILED: Timeout waiting for confirmation")

        client.loop_stop()
        client.disconnect()
        
    except Exception as e:
        print(f"Test failed with exception: {e}")

if __name__ == "__main__":
    test_confirmation()
