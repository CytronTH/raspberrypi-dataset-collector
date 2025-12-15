import yaml
import sys
import os
import platform
import multiprocessing

CONFIG_PATH = "/home/pi/dataset_collector/camera_config.yaml"

def detect_system_performance():
    """
    Detects if the system is 'high' or 'low' performance.
    Criteria for Low:
    - 'Zero' in model name (Pi Zero/Zero 2)
    - Single core (though Zero 2 is quad core, it's slow)
    - Low RAM (not easily checked without extra libs, but model name is good proxy)
    """
    try:
        # Check /proc/cpuinfo for model name on Raspberry Pi
        if os.path.exists("/proc/cpuinfo"):
            with open("/proc/cpuinfo", "r") as f:
                content = f.read()
                if "Zero" in content: # Covers Zero and Zero 2
                    return "low"
        
        # Fallback: Check CPU count. 
        # Pi Zero 1 is single core. Zero 2 is Quad. Pi 3/4/5 are Quad.
        # But Zero 2 is significantly slower than Pi 4.
        # So "Zero" check is best.
        
        # If running on non-Pi (dev machine), treat as high
        return "high"
    except Exception as e:
        print(f"Error detecting system performance: {e}", file=sys.stderr)
        return "high" # Default to high

def load_config():
    """Loads the camera configuration from the YAML file."""
    if not os.path.exists(CONFIG_PATH):
        default_config = {"cameras": {}, "performance_mode": "auto"}
    else:
        try:
            with open(CONFIG_PATH, 'r') as f:
                config = yaml.safe_load(f)
                if config is None:
                    config = {"cameras": {}}
                
                default_config = config
        except Exception as e:
            print(f"Error loading config: {e}", file=sys.stderr)
            default_config = {"cameras": {}}
    
    # Resolve Performance Mode
    perf_setting = default_config.get("performance_mode", "auto")
    if perf_setting == "auto":
        resolved_mode = detect_system_performance()
    else:
        resolved_mode = perf_setting
    
    # Inject resolved mode into config object (runtime only, doesn't save to file unless saved later)
    default_config["_resolved_performance_mode"] = resolved_mode
    default_config["performance_mode"] = perf_setting # Ensure the setting exists
    
    return default_config

def save_config(config):
    """Saves the configuration to the YAML file."""
    try:
        # Create a copy to avoid modifying the runtime object
        config_to_save =config.copy()
        
        # Remove internal keys (starting with _)
        keys_to_remove = [k for k in config_to_save.keys() if k.startswith('_')]
        for k in keys_to_remove:
            del config_to_save[k]

        with open(CONFIG_PATH, 'w') as f:
            yaml.dump(config_to_save, f, default_flow_style=False)
    except Exception as e:
        print(f"Error saving config: {e}", file=sys.stderr)




def generate_default_config(config, detected_cameras):
    """Generates a default configuration for any new cameras."""
    config_changed = False
    

        
    for cam_key, cam_info in detected_cameras.items():
        if cam_key not in config['cameras']:
            print(f"New camera detected: {cam_info['friendly_name']}. Adding to config.", file=sys.stderr)
            config_changed = True
            if cam_info['type'] == 'pi':
                config['cameras'][cam_key] = {
                    'path': cam_info['path'],
                    'friendly_name': cam_info['friendly_name'],
                    'type': 'pi',
                    'resolutions': ['640x480', '800x600', '1280x720', '1920x1080', '2304x1296', '4608x2592'],
                    'has_autofocus': True,
                    'shutter_speed_range': [30, 1000]
                }
            else: # usb
                config['cameras'][cam_key] = {
                    'path': cam_info['path'],
                    'friendly_name': cam_info['friendly_name'],
                    'type': 'usb',
                    'resolutions': ['640x480', '800x600', '1280x720', '1920x1080'],
                    'has_autofocus': False,
                    'shutter_speed_range': "unavailable"
                }
    
    # Remove disconnected cameras
    # List keys to avoid runtime error during iteration
    for cam_key in list(config['cameras'].keys()):
        if cam_key not in detected_cameras:
            print(f"Camera disconnected: {cam_key}. Removing from config.", file=sys.stderr)
            del config['cameras'][cam_key]
            config_changed = True
    
    if config_changed:
        save_config(config)
    
    return config
    

MQTT_CONFIG_PATH = "/home/pi/dataset_collector/mqtt_config.json"

def load_mqtt_config():
    """Loads the MQTT configuration from the JSON file."""
    import json
    if not os.path.exists(MQTT_CONFIG_PATH):
        # Fallback: Try to load from camera_config.yaml (Migration)
        main_config = load_config()
        if 'mqtt' in main_config:
            print("Migrating MQTT config from YAML to JSON...", file=sys.stderr)
            mqtt_config = main_config['mqtt']
            save_mqtt_config(mqtt_config)
            return mqtt_config
        
        return {
            'broker': 'localhost',
            'port': 1883,
            'topic': 'capture/trigger',
            'username': '',
            'password': ''
        }

    try:
        with open(MQTT_CONFIG_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading MQTT config: {e}", file=sys.stderr)
        return {
            'broker': 'localhost',
            'port': 1883,
            'topic': 'capture/trigger',
            'username': '',
            'password': ''
        }

def save_mqtt_config(config):
    """Saves the MQTT configuration to the JSON file."""
    import json
    try:
        with open(MQTT_CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error saving MQTT config: {e}", file=sys.stderr)