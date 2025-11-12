# Camera Configuration

This document explains how to configure the camera settings in the `camera_config.yaml` file. The configuration allows you to customize the behavior of each connected camera.

## Configuration Options

The `camera_config.yaml` file contains a `cameras` section, which is a dictionary of camera configurations. Each camera is identified by a unique key (e.g., `pi_0`, `usb_1`).

Here are the available options for each camera:

- **`path`**: (Required) The hardware path of the camera. For Pi cameras, this is usually 0, 1, etc. For USB cameras, it's the device path (e.g., `/dev/video0`, `/dev/video1`, etc.).
- **`name`**: (Required) A user-friendly name for the camera that will be displayed in the user interface.
- **`type`**: (Required) The type of the camera. This can be either `pi` for a Raspberry Pi camera or `usb` for a USB camera.
- **`resolutions`**: (Required) A list of supported resolutions for the camera. The format for each resolution is `widthxheight` (e.g., `1920x1080`).
- **`has_autofocus`**: (Required) Indicates whether the camera has autofocus capabilities. Set to `true` or `false`. This is typically `true` for newer Pi cameras and `false` for most USB cameras.
- **`shutter_speed_range`**: (Required) The range of supported shutter speeds for the camera. This can be one of the following:
    - A list of two numbers representing the minimum and maximum shutter speed values in microseconds (e.g., `[30, 1000]`).
    - The string `"unavailable"` if the camera's shutter speed cannot be controlled.

## Example Configurations

Here are some example configurations for different camera types.

### Raspberry Pi Camera

This example shows a configuration for a Raspberry Pi camera with autofocus and a specific shutter speed range.

```yaml
cameras:
  pi_0:
    has_autofocus: true
    path: 0
    name: PiCamera 0 (imx708)
    resolutions:
    - 640x480
    - 800x600
    - 1280x720
    - 1920x1080
    - 2304x1296
    - 4608x2592
    shutter_speed_range:
    - 30
    - 1000
    type: pi
```

### USB Camera

This example shows a configuration for a USB camera. USB cameras typically don't have autofocus, and their shutter speed is often not adjustable, so `shutter_speed_range` is set to `"unavailable"`.

```yaml
cameras:
  usb_0:
    has_autofocus: false
    path: /dev/video0
    name: USB Webcam
    resolutions:
    - 640x480
    - 800x600
    - 1280x720
    - 1920x1080
    shutter_speed_range: "unavailable"
    type: usb
```

## Editing the Configuration

You can edit the `camera_config.yaml` file directly or use the "Edit Config" button in the web interface. After saving your changes, the application will automatically reload the new configuration.
