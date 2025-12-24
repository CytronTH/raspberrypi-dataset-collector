#!/bin/bash

# Pi Zero 2W Setup Script for Dataset Collector
# This script installs system dependencies, sets up a virtual environment,
# and configures the app to run on boot.

set -e

echo "=== Pi Zero 2W Setup ==="

# 1. Update System & Install System Dependencies
echo "[1/5] Installing system dependencies..."
sudo apt-get update
# Swapped specific libs for more generic/modern ones compatible with Trixie/Bookworm
# Added python3-picamera2 python3-numpy python3-opencv python3-paramiko python3-yaml python3-pil as it is a system package, not on PyPI
sudo apt-get install -y python3-venv python3-pip libopenblas-dev libopenjp2-7 libtiff-dev libjpeg-dev python3-picamera2 python3-numpy python3-opencv python3-paramiko python3-yaml python3-pil python3-websockets

# 2. Increase Swap (Critical for limited RAM during install)
echo "[2/5] Checking swap space..."
if [ ! -f /etc/dphys-swapfile ]; then
    echo "dphys-swapfile not found. Installing..."
    sudo apt-get install -y dphys-swapfile
fi

# Read current swap size, defaulting to 0 if not found
SWAP_SIZE=$(grep "CONF_SWAPSIZE" /etc/dphys-swapfile 2>/dev/null | cut -d= -f2 || echo "0")
# Sanitize input (remove spaces/newlines)
SWAP_SIZE=$(echo "$SWAP_SIZE" | tr -d '[:space:]')

if [ -z "$SWAP_SIZE" ]; then
    SWAP_SIZE=0
fi

if [ "$SWAP_SIZE" -lt 1024 ]; then
    echo "Increasing swap to 1024MB for installation..."
    # If conf exists, replace; if not, append.
    if grep -q "CONF_SWAPSIZE" /etc/dphys-swapfile; then
        sudo sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=1024/' /etc/dphys-swapfile
    else
        echo "CONF_SWAPSIZE=1024" | sudo tee -a /etc/dphys-swapfile
    fi
    sudo /etc/init.d/dphys-swapfile restart
fi

# 3. Setup Virtual Environment
echo "[3/5] Setting up Virtual Environment (with system packages for picamera2)..."
# We need --system-site-packages because picamera2 is installed via apt
if [ -d "venv" ]; then
    echo "Existing venv found. Re-creating to ensure system-site-packages..."
    rm -rf venv
fi
python3 -m venv --system-site-packages venv
source venv/bin/activate

# 4. Install Python Requirements
echo "[4/5] Installing Python libraries (this may take a while)..."
# Use piwheels to avoid building from source where possible
pip install --upgrade pip
pip install --extra-index-url https://www.piwheels.org/simple -r requirements.txt

# 5. Create Service File (Optional Auto-start)
echo "[5/5] Creating systemd service..."
SERVICE_FILE="dataset_collector.service"
CURRENT_DIR=$(pwd)
USER_NAME=$(whoami)

cat <<EOF > $SERVICE_FILE
[Unit]
Description=Dataset Collector WebUI
After=network.target

[Service]
User=$USER_NAME
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/venv/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

echo "Done!"
echo "To run manually: source venv/bin/activate && python3 main.py"
echo "To install service: sudo mv $SERVICE_FILE /etc/systemd/system/ && sudo systemctl enable dataset_collector && sudo systemctl start dataset_collector"
