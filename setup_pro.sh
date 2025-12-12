#!/bin/bash

# Dataset Collector Installer - PRO VERSION
# Optimized for Raspberry Pi 4 / 5

set -e

echo "=== Raspberry Pi Pro Setup ==="

# 1. Update System
echo "[1/5] Updating system packages..."
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip libopenblas-dev libopenjp2-7 libtiff-dev libjpeg-dev python3-picamera2

# 2. Setup Virtual Environment (Skip Swap on Pro)
echo "[2/5] Setting up Virtual Environment..."
if [ -d "venv" ]; then
    rm -rf venv
fi
python3 -m venv --system-site-packages venv
source venv/bin/activate

# 3. Apply Pro Configuration
echo "[3/5] Applying Pro Configuration..."
# Config copy removed by user request. App will auto-detect config.
if [ -f "camera_config.yaml" ]; then
    echo " -> Existing config found. Keeping it."
else
    echo " -> No config found. App will generate default config on first run."
fi

# 4. Install Dependencies
echo "[4/5] Installing Python libraries..."
pip install --upgrade pip
pip install --extra-index-url https://www.piwheels.org/simple -r requirements.txt

# 5. Create Service
echo "[5/5] Creating systemd service..."
SERVICE_FILE="dataset_collector.service"
CURRENT_DIR=$(pwd)
USER_NAME=$(whoami)

cat <<EOF > $SERVICE_FILE
[Unit]
Description=Dataset Collector WebUI (Pro)
After=network.target

[Service]
User=$USER_NAME
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/venv/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

echo "========================================"
echo "Pro Setup Complete!"
echo "To run manually: source venv/bin/activate && python3 main.py"
echo "========================================"
