#!/bin/bash

# Dataset Collector Installer - LITE VERSION
# Optimized for Raspberry Pi Zero 2 W

set -e

echo "=== Pi Zero 2W (Lite) Setup ==="

# 1. Update System
echo "[1/6] Updating system packages..."
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip libopenblas-dev libopenjp2-7 libtiff-dev libjpeg-dev python3-picamera2 python3-numpy

# 2. Force Swap Configuration (Critical for Zero 2W)
echo "[2/6] Configuring Swap Memory..."
CURRENT_SWAP=$(grep "CONF_SWAPSIZE" /etc/dphys-swapfile | cut -d= -f2)
if [ "$CURRENT_SWAP" -lt 1024 ]; then
    echo " -> Increasing swap to 1024MB..."
    sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=1024/' /etc/dphys-swapfile
    sudo /etc/init.d/dphys-swapfile restart
else
    echo " -> Swap already sufficient."
fi

# 3. Apply Lite Configuration
echo "[3/6] Applying Lite Configuration..."
# Config copy removed by user request. App will auto-detect config.
if [ -f "camera_config.yaml" ]; then
    echo " -> Existing config found. Keeping it."
else
    echo " -> No config found. App will generate default config on first run."
fi

# 4. Setup Virtual Environment
echo "[4/6] Setting up Virtual Environment..."
if [ -d "venv" ]; then
    rm -rf venv
fi
python3 -m venv --system-site-packages venv
source venv/bin/activate

# 5. Install Dependencies
echo "[5/6] Installing Python libraries..."
pip install --upgrade pip
pip install --extra-index-url https://www.piwheels.org/simple -r requirements.txt

# 6. Create Service
echo "[6/6] Creating systemd service..."
SERVICE_FILE="dataset_collector.service"
CURRENT_DIR=$(pwd)
USER_NAME=$(whoami)

cat <<EOF > $SERVICE_FILE
[Unit]
Description=Dataset Collector WebUI (Lite)
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
echo "Lite Setup Complete!"
echo "To run manually: source venv/bin/activate && python3 main.py"
echo "========================================"
