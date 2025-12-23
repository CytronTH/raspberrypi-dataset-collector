<img width="2816" height="1536" alt="logo" src="https://github.com/user-attachments/assets/f77186d2-3618-454b-943b-a36dc161fadf" />

Dataset Collector for Raspberry Pi

A web-based interface for capturing and managing datasets using Raspberry Pi cameras (and USB cameras). This tool allows you to control multiple cameras, view live feeds, trigger captures via a web UI or MQTT, and automatically transfer files to a remote server via SFTP.

## Features

-   **Multi-Camera Support**: Automatically detects and controls Raspberry Pi cameras and USB webcams.
-   **Live Preview**: Low-latency MJPEG video feeds from all connected cameras.
-   **Web Interface**:
    -   **Dashboard (Grid View)**: Monitor all cameras simultaneously with live stats.
    -   **Single Camera View**: Fine-grained control with manual focus, shutter speed, and resolution settings.
    -   **SFTP Configuration**: Dedicated page to configure auto-transfer settings.
    -   **Config Editor**: Edit camera configurations (YAML) and MQTT settings directly from the browser.
    -   **Activity Log**: Real-time logging of capture events and system status.
    -   **System Monitor**: Real-time tracking of CPU, RAM, and Disk usage (with performance alerts).
-   **Auto SFTP Transfer**: 
    -   Automatically uploads captured images to a remote server after every 10 shots.
    -   **Auto-Delete**: Optionally deletes local files immediately after successful upload to save space.
    -   **Toggle**: Enable/Disable the feature easily via the WebUI.
-   **MQTT Integration**: 
    -   Remote capture triggering.
    -   Unique capability reporting using device hostname.
    -   Status reporting (`online`/`offline`).
-   **Smart File Management**: 
    -   Organize captures into custom directories via the integrated File Explorer.
    -   Automatic filename generation with configurable prefixes.

## Prerequisites

-   **Hardware**: Raspberry Pi (tested on Pi 5 and Pi Zero 2 W) with Raspberry Pi OS (Bookworm or later recommended).
-   **Software**: Python 3.11+, `libcamera`, `picamera2` (usually pre-installed on RPi OS).

## Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/CytronTH/raspberrypi-dataset-collector.git
    cd raspberrypi-dataset-collector
    ```

2.  **Run Setup Script:**

    **Option A: For Raspberry Pi Zero 2 W**
    *Optimized for low-power devices. Uses system packages to skip compilation vs heavier pip installs. Enables swap.*
    ```bash
    chmod +x setup_zero.sh
    ./setup_zero.sh
    ```

    **Option B: For Raspberry Pi 4 / 5 (Pro Version)**
    *Recommended for powerful devices. Skips swap setup and defaults to 1080p resolution.*
    ```bash
    chmod +x setup_pro.sh
    ./setup_pro.sh
    ```

3.  **Run the Application:**
    The setup script creates a virtual environment. Activate it and run:
    ```bash
    source venv/bin/activate
    python3 main.py
    ```

4.  **Access the Web Interface:**
    Open your browser and navigate to `http://<your-pi-ip>:8000`.

## Configuration

### Camera Configuration
Settings are stored in `camera_config.yaml`. 
-   **Auto-Detection**: The system automatically detects connected cameras and updates the config file with their supported resolutions and capabilities.
-   **Editor**: You can fine-tune these settings (e.g., friendly names) via the **Editor** page in the WebUI.

### MQTT Configuration
MQTT settings (Broker, Port, Topic, Auth) can be configured in the **Editor** page.
-   **Status Topic**: `dataset_collector/{hostname}/status` (Publishes "online"/"offline")
-   **Trigger Topic**: Configurable (Default: `capture/trigger`)
-   **Capture Finished Topic**: `dataset_collector/{hostname}/capture/finished`

### SFTP Configuration
Navigate to the **SFTP Config** page in the sidebar to set up:
-   **Host/Port/User/Pass**: Connection details.
-   **Remote Path**: Where files will be uploaded.
-   **Enable Auto-Transfer**: Toggle on/off. (Default: Off)

## Usage

1.  **Connect**: Navigate to the WebUI.
2.  **Compose**: Use the live preview to frame your shots. Click on a camera for a larger view and manual focus control.
3.  **Capture**: Click the **Capture** button (or press **Spacebar**) to take photos.
4.  **Transfer**: If SFTP is enabled, photos will automatically upload and clear from the device after every 10 captures.

## License

[MIT License](LICENSE)
