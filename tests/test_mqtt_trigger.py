import paho.mqtt.publish as publish
import time
import sys
from config_handler import load_config

def test_trigger():
    config = load_config()
    mqtt_config = config.get('mqtt', {})
    
    broker = mqtt_config.get('broker', 'localhost')
    port = mqtt_config.get('port', 1883)
    topic = mqtt_config.get('topic', 'capture/trigger')
    username = mqtt_config.get('username')
    password = mqtt_config.get('password')
    
    auth = None
    if username and password:
        auth = {'username': username, 'password': password}

    print(f"Sending capture trigger to {broker}:{port} on topic {topic}...")
    try:
        # payload can be empty or JSON string
        publish.single(topic, payload="{}", hostname=broker, port=port, auth=auth)
        print("Trigger sent successfully.")
        print("Check the 'captures' directory or the Web UI to confirm a new image has been taken.")
    except Exception as e:
        print(f"Failed to send trigger: {e}")
        print("Ensure the MQTT broker is running and paho-mqtt is installed.")

if __name__ == "__main__":
    test_trigger()
