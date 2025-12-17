import paramiko
import json
import os
import sys
import logging

SFTP_CONFIG_PATH = "/home/pi/dataset_collector/sftp_config.json"

class SFTPHandler:
    def __init__(self):
        self.config = self.load_config()

    def load_config(self):
        if not os.path.exists(SFTP_CONFIG_PATH):
            print(f"SFTP Config file not found at {SFTP_CONFIG_PATH}", file=sys.stderr)
            return None
        try:
            with open(SFTP_CONFIG_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading SFTP config: {e}", file=sys.stderr)
            return None

    def upload_files(self, file_paths):
        if not self.config:
            print("SFTP configuration missing. Skipping upload.", file=sys.stderr)
            return False

        host = self.config.get('host')
        port = self.config.get('port', 22)
        username = self.config.get('username')
        password = self.config.get('password')
        remote_base_path = self.config.get('remote_path', '.')

        if not host or not username:
             print("SFTP Host or Username missing in config.", file=sys.stderr)
             return False

        transport = None
        sftp = None
        success = True

        try:
            print(f"Connecting to SFTP server {host}...", file=sys.stderr)
            transport = paramiko.Transport((host, port))
            transport.connect(username=username, password=password)
            sftp = paramiko.SFTPClient.from_transport(transport)

            # Ensure remote directory exists (basic check)
            # This might fail if nested directories don't exist, strictly assumes basic path
            try:
                sftp.chdir(remote_base_path)
            except IOError:
                print(f"Remote path {remote_base_path} not found. Attempting to create...", file=sys.stderr)
                try:
                    sftp.mkdir(remote_base_path)
                    sftp.chdir(remote_base_path)
                except IOError as e:
                     print(f"Failed to create/change to remote dir: {e}", file=sys.stderr)
                     # Continue? might fail uploads
            
            for local_path in file_paths:
                if not os.path.exists(local_path):
                    print(f"File not found: {local_path}", file=sys.stderr)
                    continue
                
                filename = os.path.basename(local_path)
                print(f"Uploading {filename}...", file=sys.stderr)
                try:
                    sftp.put(local_path, filename)
                except Exception as e:
                    print(f"Failed to upload {filename}: {e}", file=sys.stderr)
                    success = False

        except Exception as e:
            print(f"SFTP connection error: {e}", file=sys.stderr)
            success = False
        finally:
            if sftp: sftp.close()
            if transport: transport.close()
        
        return success
