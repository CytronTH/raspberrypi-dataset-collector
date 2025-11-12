import yaml
import sys
import os

CONFIG_PATH = "/home/pi/dataset_collector/camera_config.yaml"

def load_config():
    """Loads the camera configuration from the YAML file."""
    if not os.path.exists(CONFIG_PATH):
        return {"cameras": {}}
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
            if config is None:
                return {"cameras": {}}
            return config
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return {"cameras": {}}

def save_config(config):
    """Saves the configuration to the YAML file."""
    try:
        with open(CONFIG_PATH, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
    except Exception as e:
        print(f"Error saving config: {e}", file=sys.stderr)


def generate_default_config(config, detected_cameras):
    """Generates a default configuration for any new cameras."""
    config_changed = False
    if 'cameras' not in config:
        config['cameras'] = {}
        
    for cam_key, cam_info in detected_cameras.items():
        if cam_key not in config['cameras']:
            print(f"New camera detected: {cam_info['friendly_name']}. Adding to config.", file=sys.stderr)
            config_changed = True
            if cam_info['type'] == 'pi':
                config['cameras'][cam_key] = {
                    'path': cam_info['path'],
                    'friendly_name': cam_info['name'],
                    'type': 'pi',
                    'resolutions': ['640x480', '800x600', '1280x720', '1920x1080', '2304x1296', '4608x2592'],
                    'has_autofocus': True,
                    'shutter_speed_range': [30, 1000]
                }
            else: # usb
                config['cameras'][cam_key] = {
                    'path': cam_info['path'],
                    'friendly_name': cam_info['name'],
                    'type': 'usb',
                    'resolutions': ['640x480', '800x600', '1280x720', '1920x1080'],
                    'has_autofocus': False,
                    'shutter_speed_range': "unavailable"
                }
    
    if config_changed:
        save_config(config)
    
    return config