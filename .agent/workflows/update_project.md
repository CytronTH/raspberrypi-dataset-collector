---
description: How to update the project without re-cloning
---
# Updating Dataset Collector

If you already have the project cloned on your Pi Zero 2W, follow these steps to update it.

## Method 1: The One-Liner (Recommended)

Run this command in your terminal inside the project directory:

```bash
./update.sh
```

*(Note: If you don't have update.sh yet, do Method 2 once, and you will get it)*

## Method 2: Manual Update

If you prefer to do it manually:

1.  **Pull the latest code**:
    ```bash
    git pull origin main
    ```

2.  **Update Python libraries** (in case we added new features):
    ```bash
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Restart the App**:
    ```bash
    sudo systemctl restart dataset_collector.service
    # OR if running manually:
    # Ctrl+C to stop, then run again:
    # python main.py
    ```
