import paho.mqtt.client as mqtt
import asyncio
import sys
import json

class MQTTClientWrapper:
    def __init__(self, broker, port, topic, callback, loop, username=None, password=None, log_callback=None):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.callback = callback
        self.loop = loop
        self.username = username
        self.password = password
        self.log_callback = log_callback
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.on_publish = self.on_publish
        self.client.on_subscribe = self.on_subscribe
        self.running = False
        self.connected = False

    def _log(self, message):
        print(message, file=sys.stderr)
        if self.log_callback:
            asyncio.run_coroutine_threadsafe(self.log_callback(message), self.loop)

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self._log(f"Connected to MQTT Broker: {self.broker}:{self.port}")
            self.connected = True
            
            # Publish Online Status
            try:
                client.publish("dataset_collector/status", payload=json.dumps({"status": "online"}), retain=True)
            except Exception as e:
                print(f"Failed to publish online status: {e}", file=sys.stderr)

            self.client.subscribe(self.topic)
            # Log handled in on_subscribe
        else:
            self._log(f"Failed to connect, return code {rc}")
            self.connected = False

    def on_disconnect(self, client, userdata, flags, rc, properties=None):
        self._log(f"Disconnected from MQTT Broker (rc={rc})")
        self.connected = False

    def on_publish(self, client, userdata, mid, reason_code=None, properties=None):
        self._log(f"Message Published (mid={mid})")

    def on_subscribe(self, client, userdata, mid, reason_code_list, properties=None):
        self._log(f"Subscribed to topic: {self.topic} (mid={mid})")

    def on_message(self, client, userdata, msg):
        try:
            payload_preview = msg.payload.decode()[:50] # Preview first 50 chars
        except:
            payload_preview = "Binary/Invalid Data"
        
        self._log(f"Received: {msg.topic} -> {payload_preview}")
        try:
            payload_str = msg.payload.decode()
            # Try to parse as JSON if possible, otherwise use default/empty settings
            try:
                data = json.loads(payload_str)
            except json.JSONDecodeError:
                data = {} # Treat as empty trigger
            
            # Run the callback in the main event loop
            if self.callback:
                 asyncio.run_coroutine_threadsafe(self.callback(data), self.loop)
                 
        except Exception as e:
            self._log(f"Error handling MQTT message: {e}")

    def start(self):
        if not self.running:
            try:
                if self.username and self.password:
                    self.client.username_pw_set(self.username, self.password)
                
                # Set Last Will and Testament (LWT)
                self.client.will_set("dataset_collector/status", payload=json.dumps({"status": "offline"}), retain=True)

                self.client.connect(self.broker, self.port, 60)
                self.client.loop_start()
                self.running = True
            except Exception as e:
                print(f"Failed to start MQTT client: {e}", file=sys.stderr)

    def stop(self):
        if self.running:
            # Publish Offline Status (Graceful)
            try:
                self.client.publish("dataset_collector/status", payload=json.dumps({"status": "offline"}), retain=True)
            except Exception as e:
                print(f"Failed to publish offline status: {e}", file=sys.stderr)
                
            self.client.loop_stop()
            self.client.disconnect()
            self.running = False
            print("MQTT Client stopped", file=sys.stderr)
