# MQTT Device Picker - Complete Documentation

## Table of Contents

1. [Introduction](#introduction)
2. [Use Cases](#use-cases)
3. [How It Works](#how-it-works)
4. [Configuration Reference](#configuration-reference)
5. [Examples](#examples)
6. [Advanced Features](#advanced-features)
7. [Troubleshooting](#troubleshooting)

---

## Introduction

The `mqtt_device_picker` is a universal custom field type for `setup.json` that enables any connector to discover and select devices from other "parent" connectors via MQTT. This powerful component provides a beautiful, searchable interface with pagination for selecting from potentially hundreds of devices.

### Key Features

- 🔍 **Real-time Search**: Instant search across multiple device fields
- 📄 **Pagination**: Efficient navigation through 100+ devices
- ⌨️ **Keyboard Navigation**: Use ← → arrow keys to navigate pages
- 🎨 **Visual Cards**: Beautiful device cards with metadata
- 📸 **Preview Support**: Show camera previews or device images
- 🔌 **Universal**: Works with any connector type (cameras, yeelight, etc.)
- ⚡ **Instant Discovery**: Uses MQTT cache for instant results
- 🎯 **Flexible Extraction**: Extract any nested fields from device state

---

## Use Cases

### 1. Video Recording from Cameras

Create a connector that records video from cameras managed by the `cameras` connector:

```json
{
  "type": "mqtt_device_picker",
  "name": "camera_source",
  "label": "Select Camera to Record",
  "config": {
    "connector_type": "cameras",
    "extract_fields": ["ip", "stream_urls.mp4", "stream_urls.rtsp"],
    "show_preview": true
  }
}
```

### 2. Light Automation

Create scenes or automation with Yeelight devices:

```json
{
  "type": "mqtt_device_picker",
  "name": "lights",
  "label": "Select Lights for Scene",
  "config": {
    "connector_type": "yeelight",
    "extract_fields": ["ip", "port", "capabilities"]
  }
}
```

### 3. Multi-Device Aggregation

Collect data from multiple IoT sensors:

```json
{
  "type": "mqtt_device_picker",
  "name": "sensor",
  "label": "Select Sensor",
  "config": {
    "connector_type": "sensors",
    "extract_fields": ["type", "unit", "location"]
  }
}
```

---

## How It Works

### Architecture

```
┌─────────────────────┐
│   Frontend (User)   │
│   - Search UI       │
│   - Device Cards    │
│   - Pagination      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Backend API        │
│  /api/mqtt/         │
│  discover-devices   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  MQTT Service       │
│  topic_cache        │
│  (All MQTT topics)  │
└─────────────────────┘
```

### Discovery Process

1. **MQTT Scanning**: Backend scans `mqtt_service.topic_cache` for matching topics
2. **Pattern Matching**: Filters topics by connector type and instance filter
3. **State Extraction**: Retrieves full device state from MQTT
4. **Client Filtering**: Frontend provides instant search across device fields
5. **Pagination**: Displays devices in pages for performance
6. **Selection**: User selects device, and configured fields are extracted
7. **Save**: Extracted data is saved to instance configuration

---

## Configuration Reference

### Required Fields

#### `connector_type`
- **Type**: `string`
- **Required**: Yes
- **Description**: Type of connector to search for devices
- **Examples**: `"cameras"`, `"yeelight"`, `"sensors"`

```json
{
  "connector_type": "cameras"
}
```

---

### Discovery Options

#### `mqtt_topic_pattern`
- **Type**: `string` (regex)
- **Required**: No
- **Default**: Auto-generated from `connector_type`
- **Description**: Custom regex pattern for matching MQTT topics
- **Example**:

```json
{
  "mqtt_topic_pattern": ".*/v1/instances/cameras_.*/devices/.*/state$"
}
```

#### `instance_filter`
- **Type**: `string` (glob pattern)
- **Required**: No
- **Default**: None
- **Description**: Filter devices by instance ID (supports `*` wildcard)
- **Examples**:

```json
{
  "instance_filter": "cameras_*"
}
```

```json
{
  "instance_filter": "cameras_main_building"
}
```

#### `base_topic_override`
- **Type**: `string`
- **Required**: No
- **Default**: Uses MQTT config base topic
- **Description**: Override base MQTT topic for discovery

```json
{
  "base_topic_override": "CustomTopic"
}
```

---

### Data Extraction

#### `extract_fields`
- **Type**: `array<string>`
- **Required**: No
- **Default**: `[]`
- **Description**: List of field paths to extract from device state
- **Supports**: Nested fields using dot notation (e.g., `"stream_urls.mp4"`)
- **Examples**:

```json
{
  "extract_fields": [
    "ip",
    "name",
    "stream_urls.mp4",
    "stream_urls.rtsp",
    "capabilities.resolution"
  ]
}
```

**Field Extraction Examples**:

| Field Path | Device State | Extracted Value |
|------------|--------------|-----------------|
| `"ip"` | `{"ip": "10.0.0.1"}` | `"10.0.0.1"` |
| `"stream_urls.mp4"` | `{"stream_urls": {"mp4": "http://..."}}` | `"http://..."` |
| `"config.enabled"` | `{"config": {"enabled": true}}` | `true` |

#### `save_mode`
- **Type**: `string`
- **Required**: No
- **Default**: `"mqtt_path"`
- **Options**: `"mqtt_path"` \| `"extracted_fields"` \| `"full_state"`
- **Description**: Determines what data is saved

**Save Mode Details**:

| Mode | Saves | Use Case |
|------|-------|----------|
| `mqtt_path` | MQTT topic path only | Just need to subscribe to device |
| `extracted_fields` | Only fields from `extract_fields` | Need specific data points |
| `full_state` | Complete device state | Need all device information |

**Example Output**:

```javascript
// save_mode: "mqtt_path"
{
  "mqtt_path": "IoT2mqtt/v1/instances/cameras_abc/devices/cam1/state",
  "device_id": "cam1",
  "instance_id": "cameras_abc"
}

// save_mode: "extracted_fields" with extract_fields: ["ip", "stream_urls.mp4"]
{
  "mqtt_path": "...",
  "device_id": "cam1",
  "instance_id": "cameras_abc",
  "extracted_data": {
    "ip": "10.0.0.1",
    "mp4": "http://10.0.0.1/stream.mp4"
  }
}

// save_mode: "full_state"
{
  "mqtt_path": "...",
  "device_id": "cam1",
  "instance_id": "cameras_abc",
  "extracted_data": {
    /* full device state object */
  }
}
```

#### `output_format`
- **Type**: `object`
- **Required**: No
- **Description**: Custom template for output structure (advanced)
- **Supports**: Template variables `{{ mqtt_topic }}`, `{{ state.field }}`

```json
{
  "output_format": {
    "device_path": "{{ mqtt_topic }}",
    "camera_ip": "{{ state.ip }}",
    "stream": "{{ state.stream_urls.mp4 }}"
  }
}
```

---

### Search & Pagination

#### `enable_search`
- **Type**: `boolean`
- **Required**: No
- **Default**: `true`
- **Description**: Enable/disable search bar

#### `searchable_fields`
- **Type**: `array<string>`
- **Required**: No
- **Default**: `["name", "device_id", "ip", "brand", "model"]`
- **Description**: Fields to search across
- **Supports**: Nested fields with dot notation

```json
{
  "searchable_fields": [
    "name",
    "device_id",
    "ip",
    "brand",
    "model",
    "location",
    "serial_number"
  ]
}
```

#### `items_per_page`
- **Type**: `number`
- **Required**: No
- **Default**: `12`
- **Description**: Number of device cards per page
- **Recommended**: Multiples of `grid_columns` (e.g., 12 for 4 columns)

```json
{
  "items_per_page": 16
}
```

---

### UI Customization

#### `show_preview`
- **Type**: `boolean`
- **Required**: No
- **Default**: `false`
- **Description**: Show image preview on device cards (for cameras)

#### `preview_field`
- **Type**: `string`
- **Required**: No (required if `show_preview: true`)
- **Default**: `"stream_urls.jpeg"`
- **Description**: Field path to preview image URL

```json
{
  "show_preview": true,
  "preview_field": "stream_urls.jpeg"
}
```

#### `card_title_field`
- **Type**: `string`
- **Required**: No
- **Default**: `"name"`
- **Description**: Field to use as card title

#### `card_subtitle_field`
- **Type**: `string`
- **Required**: No
- **Default**: `"brand"`
- **Description**: Field to use as card subtitle

#### `icon_field`
- **Type**: `string`
- **Required**: No
- **Default**: `"brand"`
- **Description**: Field to determine icon (currently based on `connector_type`)

#### `online_field`
- **Type**: `string`
- **Required**: No
- **Default**: `"online"`
- **Description**: Field indicating device online status

```json
{
  "card_title_field": "friendly_name",
  "card_subtitle_field": "model",
  "online_field": "connected"
}
```

#### `grid_columns`
- **Type**: `number`
- **Required**: No
- **Default**: `4`
- **Range**: `1-6`
- **Description**: Number of columns in device grid

```json
{
  "grid_columns": 3
}
```

---

## Examples

### Example 1: Camera Recorder (Full Featured)

```json
{
  "id": "select_camera",
  "type": "form",
  "title": "Select Camera",
  "description": "Choose a camera to record from",
  "schema": {
    "fields": [
      {
        "type": "mqtt_device_picker",
        "name": "camera_device",
        "label": "Camera Source",
        "description": "Search by name, IP, or brand",
        "required": true,
        "config": {
          "connector_type": "cameras",
          "extract_fields": [
            "ip",
            "stream_urls.mp4",
            "stream_urls.rtsp",
            "name",
            "brand",
            "model"
          ],
          "save_mode": "extracted_fields",
          "show_preview": true,
          "preview_field": "stream_urls.jpeg",
          "card_title_field": "name",
          "card_subtitle_field": "brand",
          "online_field": "online",
          "items_per_page": 12,
          "grid_columns": 4,
          "searchable_fields": [
            "name",
            "device_id",
            "ip",
            "brand",
            "model"
          ]
        }
      }
    ]
  }
}
```

**Access extracted data in next step**:

```json
{
  "instance": {
    "config": {
      "camera_mqtt": "{{ form.select_camera.camera_device.mqtt_path }}",
      "camera_ip": "{{ form.select_camera.camera_device.extracted_data.ip }}",
      "stream_url": "{{ form.select_camera.camera_device.extracted_data.mp4 }}"
    }
  }
}
```

### Example 2: Yeelight Automation (Simple)

```json
{
  "id": "select_light",
  "type": "form",
  "schema": {
    "fields": [
      {
        "type": "mqtt_device_picker",
        "name": "light",
        "label": "Select Light",
        "required": true,
        "config": {
          "connector_type": "yeelight",
          "extract_fields": ["ip", "port", "name"],
          "save_mode": "extracted_fields",
          "items_per_page": 9,
          "grid_columns": 3
        }
      }
    ]
  }
}
```

### Example 3: Multiple Devices (Advanced)

For selecting multiple devices, use multi-device support in your flow:

```json
{
  "multi_device": {
    "enabled": true,
    "max_devices": 10,
    "loop_from_step": "select_camera",
    "loop_to_step": "select_camera"
  }
}
```

---

## Advanced Features

### Nested Field Extraction

Extract deeply nested data:

```json
{
  "extract_fields": [
    "config.stream.video.codec",
    "capabilities.resolution.max",
    "metadata.installation.location"
  ]
}
```

### Custom MQTT Patterns

Use regex for complex filtering:

```json
{
  "mqtt_topic_pattern": "^IoT2mqtt.*/v1/instances/(cameras|surveillance)_.*/devices/.*/state$"
}
```

### Template Variables

Access selected device data anywhere in subsequent steps:

| Variable | Description |
|----------|-------------|
| `{{ form.STEP_ID.FIELD_NAME.mqtt_path }}` | Full MQTT topic path |
| `{{ form.STEP_ID.FIELD_NAME.device_id }}` | Device ID |
| `{{ form.STEP_ID.FIELD_NAME.instance_id }}` | Instance ID |
| `{{ form.STEP_ID.FIELD_NAME.extracted_data.FIELD }}` | Extracted field value |

**Example**:

```json
{
  "summary": {
    "sections": [
      {
        "label": "Camera Name",
        "value": "{{ form.select_camera.camera_device.extracted_data.name }}"
      },
      {
        "label": "Camera IP",
        "value": "{{ form.select_camera.camera_device.extracted_data.ip }}"
      }
    ]
  }
}
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `←` (Left Arrow) | Previous page |
| `→` (Right Arrow) | Next page |

---

## Troubleshooting

### No Devices Found

**Problem**: Component shows "No devices found"

**Solutions**:

1. **Check MQTT Connection**:
   - Verify MQTT service is connected
   - Check MQTT broker is running

2. **Verify Connector Type**:
   - Ensure `connector_type` matches actual connector name
   - Check existing instances: `IoT2mqtt/v1/instances/{connector_type}_*`

3. **Check Instance Filter**:
   - If using `instance_filter`, verify pattern is correct
   - Try removing filter to see all devices

4. **Verify Device Publishing**:
   - Ensure target devices are publishing to MQTT
   - Check MQTT topics at `/api/mqtt/topics`

### Search Not Working

**Problem**: Search returns no results

**Solutions**:

1. **Check Searchable Fields**:
   - Verify `searchable_fields` includes fields that exist in device state
   - Use browser DevTools to inspect device state structure

2. **Case Sensitivity**:
   - Search is case-insensitive, but field names are case-sensitive

3. **Field Path**:
   - Ensure nested field paths use correct dot notation
   - Example: `"stream_urls.mp4"` not `"stream_urls/mp4"`

### Preview Images Not Loading

**Problem**: Camera preview images don't display

**Solutions**:

1. **Check Preview Field**:
   - Verify `preview_field` path is correct
   - Common: `"stream_urls.jpeg"` or `"snapshot_url"`

2. **CORS Issues**:
   - Ensure camera allows cross-origin requests
   - Check browser console for CORS errors

3. **Authentication**:
   - Some cameras require authentication for images
   - Consider using authenticated URLs if available

### Performance Issues

**Problem**: Slow loading with many devices

**Solutions**:

1. **Reduce Items Per Page**:
   ```json
   {
     "items_per_page": 8
   }
   ```

2. **Use Instance Filter**:
   ```json
   {
     "instance_filter": "cameras_building_1"
   }
   ```

3. **Disable Previews**:
   ```json
   {
     "show_preview": false
   }
   ```

### Field Extraction Fails

**Problem**: Extracted fields are `null` or `undefined`

**Solutions**:

1. **Check Field Path**:
   - Verify field exists in device state
   - Use exact path with correct casing

2. **Inspect Device State**:
   - Check MQTT topic manually: `/api/mqtt/topics?filter=devices`
   - Verify field structure

3. **Handle Missing Fields**:
   - Use optional fields in your connector logic
   - Provide defaults when field is missing

---

## Best Practices

### 1. Choose Appropriate Grid Layout

```json
// For cameras with previews (4 columns)
{
  "grid_columns": 4,
  "items_per_page": 12
}

// For simple devices (3 columns)
{
  "grid_columns": 3,
  "items_per_page": 9
}
```

### 2. Extract Only Needed Fields

Don't extract entire state if you only need a few fields:

```json
// Good
{
  "extract_fields": ["ip", "port"],
  "save_mode": "extracted_fields"
}

// Avoid (unless necessary)
{
  "save_mode": "full_state"
}
```

### 3. Provide Good Search Fields

Include all fields users might search by:

```json
{
  "searchable_fields": [
    "name",
    "device_id",
    "ip",
    "brand",
    "model",
    "location",  // If available
    "serial_number"  // If available
  ]
}
```

### 4. Use Meaningful Labels

```json
{
  "label": "Select Camera to Record",
  "description": "Search by camera name, IP address, or brand"
}
```

### 5. Show Preview When Useful

Only enable preview for visual devices:

```json
// Cameras - Yes
{
  "connector_type": "cameras",
  "show_preview": true
}

// Lights - No (unless device has image)
{
  "connector_type": "yeelight",
  "show_preview": false
}
```

---

## API Reference

### Backend Endpoint

**POST** `/api/mqtt/discover-connector-devices`

**Request Body**:

```json
{
  "connector_type": "cameras",
  "mqtt_topic_pattern": null,
  "instance_filter": null,
  "base_topic_override": null,
  "search_query": null
}
```

**Response**:

```json
[
  {
    "mqtt_path": "IoT2mqtt/v1/instances/cameras_abc/devices/cam1/state",
    "instance_id": "cameras_abc",
    "device_id": "cam1",
    "state": {
      "online": true,
      "name": "Front Door Camera",
      "ip": "10.0.0.1",
      "brand": "Hikvision",
      "stream_urls": {
        "mp4": "http://...",
        "jpeg": "http://..."
      }
    },
    "timestamp": "2025-10-22T12:00:00Z"
  }
]
```

---

## Complete Example Connector

See `/connectors/_template-mqtt-picker/` for a complete working example with:

- Camera selection flow
- Yeelight selection flow
- Summary steps
- Instance creation

---

## Support

For issues or questions:

1. Check this documentation
2. Review example template: `/connectors/_template-mqtt-picker/`
3. Inspect MQTT topics: `GET /api/mqtt/topics`
4. Check browser DevTools console for errors
5. Review backend logs for API errors

---

## Changelog

### Version 1.0.0 (2025-10-22)

- Initial release
- Search functionality
- Pagination with keyboard navigation
- Preview support for cameras
- Nested field extraction
- Multiple save modes
- Flexible configuration options
