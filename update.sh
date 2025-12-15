#!/bin/bash
set -e

echo "=== Updating Dataset Collector ==="
echo "[1/3] Pulling latest changes..."
git pull origin main

echo "[2/3] Updating dependencies..."
# Only try to activate if venv exists
if [ -d "venv" ]; then
    source venv/bin/activate
    pip install -r requirements.txt
else
    echo "Warning: Virtual environment not found. Updating global pip packages..."
    sudo pip install -r requirements.txt
fi

echo "[3/3] Restarting Service..."
if systemctl is-active --quiet dataset_collector.service; then
    sudo systemctl restart dataset_collector.service
    echo "Service restarted."
else
    echo "Service 'dataset_collector.service' is not active. If you are running it manually, please restart it manually."
    echo "Manual restart: source venv/bin/activate && python3 main.py"
fi

echo "==================================="
echo "Update Complete!"
echo "==================================="
