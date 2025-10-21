# Template: MQTT Device Picker

This is an example template connector demonstrating how to use the `mqtt_device_picker` field type to connect to devices from other "parent" connectors (like cameras, yeelight, etc.).

## Overview

The `mqtt_device_picker` is a universal custom field that allows any connector to discover and select devices from other connectors via MQTT. This is useful for creating connectors that work with existing devices, such as:

- Video recording from cameras
- Automation with Yeelight lights
- Data processing from IoT sensors
- And many more use cases

## Features

- **Search**: Real-time search across device name, IP, brand, model, and other fields
- **Pagination**: Efficient handling of 100+ devices with keyboard navigation (← → arrow keys)
- **Visual Cards**: Beautiful device cards with optional preview images (for cameras)
- **Flexible Configuration**: Extract any fields from MQTT device state
- **Multiple Save Modes**: Choose how to save device data (MQTT path, extracted fields, or full state)

## How It Works

1. **Discovery**: Component scans MQTT for devices of specified connector type
2. **Search & Filter**: User can search devices by multiple fields
3. **Selection**: User selects device from visual cards
4. **Data Extraction**: Specified fields are extracted from device state
5. **Save**: Extracted data is saved to instance configuration

## Example Flows

### 1. Camera Selection (Full Featured)

Shows all features: preview, search, metadata display

```json
{
  "type": "mqtt_device_picker",
  "name": "camera_device",
  "config": {
    "connector_type": "cameras",
    "extract_fields": ["ip", "stream_urls.mp4", "name"],
    "show_preview": true,
    "preview_field": "stream_urls.jpeg",
    "items_per_page": 12,
    "grid_columns": 4
  }
}
```

### 2. Yeelight Selection (Simple)

Minimal configuration for simpler devices

```json
{
  "type": "mqtt_device_picker",
  "name": "light_device",
  "config": {
    "connector_type": "yeelight",
    "extract_fields": ["ip", "port"],
    "items_per_page": 9,
    "grid_columns": 3
  }
}
```

## Configuration Options

See the full documentation in `docs/mqtt_device_picker.md` for all available options.

## Usage in Your Connector

1. Copy this template to your connector directory
2. Modify `setup.json` to fit your needs
3. Configure `mqtt_device_picker` field with:
   - `connector_type`: Type of devices to discover
   - `extract_fields`: Fields to extract from device state
   - Display options (preview, card layout, etc.)
4. Use extracted data in your instance configuration via template variables

## Template Variables

Access selected device data in subsequent steps:

```
{{ form.select_camera.camera_device.mqtt_path }}
{{ form.select_camera.camera_device.device_id }}
{{ form.select_camera.camera_device.extracted_data.ip }}
{{ form.select_camera.camera_device.extracted_data.mp4 }}
```

## Notes

- Requires MQTT to be connected and running
- Only shows devices that are currently publishing to MQTT
- Search is client-side for instant results
- Supports nested field extraction (e.g., `stream_urls.mp4`)
