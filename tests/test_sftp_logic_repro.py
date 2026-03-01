
import json
import os
from sftp_handler import SFTPHandler

# Mock config
SFTP_CONFIG_PATH = "/home/pi/dataset_collector/sftp_config.json"

def test_sftp_trigger():
    # 1. Ensure config exists with batch_size = 1
    config = {
        "enabled": True,
        "host": "test_host",
        "username": "test_user",
        "password": "test_password",
        "remote_path": ".",
        "batch_size": 1
    }
    
    with open(SFTP_CONFIG_PATH, 'w') as f:
        json.dump(config, f)
        
    print(f"Created config with batch_size: {config['batch_size']}")
    
    # 2. Simulate global capture logic
    handler = SFTPHandler()
    print(f"Loaded config: {handler.config}")
    
    batch_size = handler.config.get('batch_size', 10)
    print(f"Read batch_size: {batch_size}")
    
    pending_transfers = ["test_file.jpg"]
    
    if len(pending_transfers) >= batch_size:
        print(f"SUCCESS: Trigger condition met ({len(pending_transfers)} >= {batch_size})")
    else:
        print(f"FAILURE: Trigger condition NOT met ({len(pending_transfers)} < {batch_size})")

if __name__ == "__main__":
    test_sftp_trigger()
