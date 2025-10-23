# Parasitic Connectors

## Introduction

Parasitic connectors are a unique architectural pattern in IoT2MQTT that enables extending existing device functionality without modifying the original connector code. Much like browser extensions enhance web applications or WordPress plugins add capabilities to websites, parasitic connectors attach to parent devices and publish additional state fields to their MQTT topics while maintaining completely independent control and lifecycle management.

This non-invasive extension mechanism allows you to add motion detection to cameras, attach AI object recognition to video streams, create notification layers on any device type, or build custom data transformation pipelines—all without touching the original connector implementation. Each parasitic connector runs in its own Docker container with independent configuration, restart capability, and command interface, yet seamlessly extends parent device capabilities through coordinated MQTT publishing.

## Architecture Overview

### Dual-Topic Publishing Model

Parasitic connectors implement a sophisticated dual-topic publishing strategy that maintains clean separation between connector control and device extension:

**Own Instance Namespace** - The parasitic connector publishes its operational status, health metrics, and control interface through its own instance topics:
```
iot2mqtt/v1/instances/cameras_motion_xyz/devices/camera_1/state
→ {"online": true, "status": "detecting", "fps": 30, "last_analysis": "2025-10-23..."}

iot2mqtt/v1/instances/cameras_motion_xyz/devices/camera_1/cmd
→ Accepts commands: {"sensitivity": 0.8, "enabled": true, "detection_zone": {...}}

iot2mqtt/v1/instances/cameras_motion_xyz/devices/camera_1/parasite
→ Registry: ["iot2mqtt/v1/instances/cameras_abc/devices/camera_1"]
```

**Parent Instance Extension** - The parasitic connector extends parent device functionality by publishing additional fields directly to the parent's state topic namespace:
```
iot2mqtt/v1/instances/cameras_abc/devices/camera_1/state/motion → true
iot2mqtt/v1/instances/cameras_abc/devices/camera_1/state/motion_confidence → 0.92
iot2mqtt/v1/instances/cameras_abc/devices/camera_1/state/motion_last_detected → "2025-10-23..."
```

### Device ID Inheritance Requirement

Parasitic connectors MUST use the exact same device_id as their parent device in their own device configuration. This ensures proper field association when multiple devices exist and enables UI systems to correlate parasitic extensions with their parent devices.

**Correct Configuration:**
```json
{
  "parasite_targets": [{
    "device_id": "camera_1"
  }],
  "devices": [{
    "device_id": "camera_1",  // ← MUST match parent device_id
    "name": "Motion Detector: Camera 1"
  }]
}
```

### Independent Lifecycle Management

Each parasitic connector runs in its own Docker container and maintains complete independence from parent devices:

- **Independent Restart** - Restarting a parasitic connector does not affect parent device operation
- **Independent Configuration** - Each connector has separate settings (sensitivity, thresholds, intervals)
- **Independent Monitoring** - Separate health metrics and error reporting
- **Independent Scaling** - Can run multiple parasitic connectors on different hosts

## Control Plane Separation

### Critical Architecture Decision

Parasitic connectors are controlled EXCLUSIVELY through their own instance CMD topics, NOT through parent device CMD topics. This maintains clear separation of concerns and prevents control surface conflicts.

**Why This Matters:**

Each connector manages fundamentally different capabilities with distinct configuration options. A motion detection parasitic connector might accept commands like `{"sensitivity": 0.8, "enabled": false, "detection_zone": {...}}` while the parent camera accepts `{"brightness": 50, "zoom": 2.0, "pan": 45}`. These represent independent concerns that should not interfere with each other.

**Control Flow Examples:**

Control parent camera (brightness, zoom, pan):
```bash
mosquitto_pub -t 'iot2mqtt/v1/instances/cameras_abc/devices/camera_1/cmd' \
  -m '{"zoom": 2.0, "brightness": 60}'
```

Control motion detector parasitic connector (sensitivity, detection zones):
```bash
mosquitto_pub -t 'iot2mqtt/v1/instances/cameras_motion_xyz/devices/camera_1/cmd' \
  -m '{"sensitivity": 0.9, "enabled": true}'
```

**Security Implications:**

Separate control planes enable granular access control. You can grant users permission to control motion detection settings without giving them access to camera controls, or vice versa. This isolation prevents accidental misconfiguration and enables role-based access patterns.

## Configuration Structure

### Parasite Targets Array

Parasitic connectors declare their parent devices through the `parasite_targets` array in instance configuration:

```json
{
  "instance_id": "cameras_motion_xyz",
  "connector_type": "cameras-motion",
  "config": {
    "parasite_targets": [
      {
        "mqtt_path": "iot2mqtt/v1/instances/cameras_abc/devices/camera_1",
        "device_id": "camera_1",
        "instance_id": "cameras_abc",
        "extracted_data": {
          "rtsp": "rtsp://10.0.20.111:554/stream",
          "ip": "10.0.20.111",
          "name": "Front Door Camera"
        }
      }
    ],
    "sensitivity": 0.7,
    "check_interval": 1
  },
  "devices": [
    {
      "device_id": "camera_1",
      "name": "Motion Detection: Front Door Camera"
    }
  ]
}
```

### Field Descriptions

**Required Fields:**

- `mqtt_path` - Complete MQTT path to parent device (without /state suffix). Used for both reading parent state and publishing extension fields.
- `device_id` - Parent device identifier. MUST match between parasite and parent for proper field association.
- `instance_id` - Parent instance identifier. Used for logging and debugging relationship tracking.

**Optional Fields:**

- `extracted_data` - Dictionary containing parent device information extracted during setup (IPs, stream URLs, credentials, etc.). Populated automatically by mqtt_device_picker field type.

### Integration with mqtt_device_picker

The `mqtt_device_picker` field type in setup flows automatically populates all required parasite_targets fields:

```json
{
  "type": "mqtt_device_picker",
  "name": "camera_device",
  "config": {
    "connector_type": "cameras",
    "extract_fields": ["ip", "stream_urls.rtsp", "name"],
    "save_mode": "extracted_fields"
  }
}
```

The picker returns a complete parasite target object:
```json
{
  "mqtt_path": "iot2mqtt/v1/instances/cameras_abc/devices/camera_1",
  "device_id": "camera_1",
  "instance_id": "cameras_abc",
  "extracted_data": {
    "ip": "10.0.20.111",
    "rtsp": "rtsp://10.0.20.111:554/stream",
    "name": "Front Door Camera"
  }
}
```

## Implementation Guide

### Step 1: Create Connector Structure

```python
from shared.base_connector import BaseConnector
from typing import Dict, Any, Optional

class Connector(BaseConnector):
    """
    Motion Detection Parasitic Connector

    Extends camera devices with motion detection capability by analyzing
    RTSP streams and publishing motion events to parent camera topics.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Verify this is configured as parasitic connector
        if not self.is_parasite_mode:
            raise ValueError("This connector requires parasite_targets configuration")

        # Initialize motion detection engine
        self.motion_detector = MotionDetector(
            sensitivity=self.config.get('sensitivity', 0.7),
            method=self.config.get('method', 'ffmpeg')
        )
```

### Step 2: Initialize Connection to Parent Devices

```python
def initialize_connection(self):
    """
    Initialize motion detection for each parent device.

    Called automatically by BaseConnector after MQTT connection and
    parasite subscriptions are established.
    """
    for target in self.parasite_targets:
        device_id = target['device_id']

        # Extract stream URL from parent device data
        extracted_data = target.get('extracted_data', {})
        rtsp_url = extracted_data.get('rtsp')

        if not rtsp_url:
            logger.warning(f"No RTSP URL found for device {device_id}, checking parent state...")

            # Alternatively, read from parent state cache
            parent_state = self.get_parent_state(target['mqtt_path'])
            if parent_state:
                rtsp_url = parent_state.get('stream_urls', {}).get('rtsp')

        if rtsp_url:
            # Start motion analysis for this stream
            self.motion_detector.add_stream(device_id, rtsp_url)
            logger.info(f"Started motion detection for {device_id}")
        else:
            logger.error(f"Cannot start motion detection for {device_id}: No stream URL")
```

### Step 3: Implement Device State Logic

```python
def get_device_state(self, device_id: str, device_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Return connector's own operational state and publish parasitic fields.

    This method is called regularly by BaseConnector's polling loop.
    Use it to both return own state and extend parent devices.
    """
    # Own operational state (published to own instance topic)
    own_state = {
        "online": True,
        "status": "detecting",
        "fps": self.motion_detector.get_fps(device_id),
        "last_analysis": datetime.now().isoformat()
    }

    # Find parasite target for this device
    for target in self.parasite_targets:
        if target['device_id'] == device_id:
            # Get motion detection results
            motion_result = self.motion_detector.get_motion_state(device_id)

            # Publish extension fields to PARENT device topic
            self.publish_parasite_fields(target['mqtt_path'], {
                "motion": motion_result['detected'],
                "motion_confidence": motion_result['confidence'],
                "motion_last_detected": motion_result.get('last_detected'),
                "motion_detection_enabled": True
            })

            logger.debug(f"Published motion fields to parent {target['mqtt_path']}")

    return own_state
```

### Step 4: Implement Command Handling

```python
def set_device_state(self, device_id: str, device_config: Dict[str, Any],
                     state: Dict[str, Any]) -> bool:
    """
    Handle commands sent to THIS connector's CMD topic.

    Commands are sent to: iot2mqtt/v1/instances/cameras_motion_xyz/devices/camera_1/cmd
    NOT to parent camera's CMD topic.
    """
    try:
        # Handle sensitivity adjustment
        if 'sensitivity' in state:
            sensitivity = float(state['sensitivity'])
            self.motion_detector.set_sensitivity(device_id, sensitivity)
            logger.info(f"Updated sensitivity for {device_id}: {sensitivity}")

        # Handle enable/disable
        if 'enabled' in state:
            enabled = bool(state['enabled'])
            if enabled:
                self.motion_detector.enable(device_id)
            else:
                self.motion_detector.disable(device_id)
            logger.info(f"Motion detection {('enabled' if enabled else 'disabled')} for {device_id}")

        return True

    except Exception as e:
        logger.error(f"Error setting state for {device_id}: {e}")
        return False
```

### Step 5: Cleanup

```python
def cleanup_connection(self):
    """
    Clean up resources when connector stops.

    Called automatically by BaseConnector during shutdown.
    """
    logger.info("Stopping motion detector...")
    self.motion_detector.stop()
    logger.info("Motion detector stopped")
```

## MQTT Topic Structure

### Complete Topic Hierarchy

For a parasitic motion detection connector attached to a camera:

**Parasitic Connector (Own Instance):**
```
iot2mqtt/v1/instances/cameras_motion_xyz/
├── status → "online"
├── devices/camera_1/
│   ├── state → {"online": true, "status": "detecting", "fps": 30}
│   ├── state/online → true
│   ├── state/status → "detecting"
│   ├── state/fps → 30
│   ├── cmd ← CONTROL INTERFACE (accepts: sensitivity, enabled, detection_zone)
│   └── parasite → ["iot2mqtt/v1/instances/cameras_abc/devices/camera_1"]
└── meta/
    ├── devices_list
    └── info
```

**Parent Camera (Extended Fields):**
```
iot2mqtt/v1/instances/cameras_abc/
├── status → "online"
├── devices/camera_1/
│   ├── state → {"online": true, "stream_urls": {...}, "motion": true, ...}
│   ├── state/online → true
│   ├── state/stream_urls → {...}
│   ├── state/motion → true ← Published by parasite
│   ├── state/motion_confidence → 0.92 ← Published by parasite
│   ├── state/motion_last_detected → "2025-10-23..." ← Published by parasite
│   └── cmd ← Parent camera control (accepts: zoom, brightness, pan)
```

### Topic Permissions and Access

**Read Access:**
- Parasitic connectors subscribe to parent `/state` topics (read-only)
- UI/monitoring systems can read both instance namespaces

**Write Access:**
- Parent connectors publish to their own `/state` topics
- Parasitic connectors publish additional fields to parent `/state/{field}` sub-topics
- Each connector handles only its own `/cmd` topic

## Advanced Patterns

### Multi-Device Parasitism

A single parasitic connector instance can extend multiple parent devices:

```json
{
  "parasite_targets": [
    {
      "mqtt_path": "iot2mqtt/v1/instances/cameras_abc/devices/front_door",
      "device_id": "front_door",
      "extracted_data": {"rtsp": "rtsp://10.0.20.111/..."}
    },
    {
      "mqtt_path": "iot2mqtt/v1/instances/cameras_abc/devices/back_door",
      "device_id": "back_door",
      "extracted_data": {"rtsp": "rtsp://10.0.20.112/..."}
    }
  ],
  "devices": [
    {"device_id": "front_door", "name": "Motion: Front Door"},
    {"device_id": "back_door", "name": "Motion: Back Door"}
  ]
}
```

### Chained Parasitic Connectors

Parasitic connectors can extend other parasitic connectors, creating processing chains:

```
cameras → cameras-motion → cameras-recorder
                        ↘
                          cameras-ai → cameras-telegram
```

Example: cameras-telegram reads motion events from cameras-motion and object detection from cameras-ai to send intelligent notifications ("Person detected at front door").

### Conditional Field Publishing

Publish fields only when meaningful data is available:

```python
def get_device_state(self, device_id, device_config):
    own_state = {"online": True}

    for target in self.parasite_targets:
        if target['device_id'] == device_id:
            motion = self.detector.get_motion(device_id)

            # Only publish when motion detected (reduce MQTT traffic)
            if motion['detected']:
                self.publish_parasite_fields(target['mqtt_path'], {
                    "motion": True,
                    "motion_confidence": motion['confidence'],
                    "motion_last_detected": datetime.now().isoformat()
                })
            else:
                # Clear motion flag
                self.publish_parasite_fields(target['mqtt_path'], {
                    "motion": False
                })

    return own_state
```

### Performance Considerations

**Update Interval Tuning** - Parasitic connectors can use different update intervals than parent devices:
```json
{
  "update_interval": 1,  // Check motion every second
  // Parent camera might update every 10 seconds
}
```

**Selective Caching** - Use `get_parent_state()` to cache expensive parent data lookups:
```python
# Cache parent state to avoid repeated parsing
parent_state = self.get_parent_state(target['mqtt_path'])
if parent_state:
    # Reuse cached stream URLs, IPs, configuration
    stream_url = parent_state.get('stream_urls', {}).get('rtsp')
```

## Real-World Examples

### Example 1: AI Object Recognition on Cameras

```python
class Connector(BaseConnector):
    """Parasitic AI object detector for camera streams"""

    def initialize_connection(self):
        from ultralytics import YOLO
        self.model = YOLO('yolov8n.pt')

        for target in self.parasite_targets:
            jpeg_url = target['extracted_data'].get('jpeg')
            if jpeg_url:
                logger.info(f"AI detection ready for {target['device_id']}")

    def get_device_state(self, device_id, device_config):
        own_state = {"online": True, "model": "yolov8n"}

        for target in self.parasite_targets:
            if target['device_id'] == device_id:
                # Grab frame from parent camera
                frame = self._fetch_frame(target['extracted_data']['jpeg'])

                # Run YOLO detection
                results = self.model(frame)
                counts = self._count_objects(results)

                # Publish to parent camera topic
                self.publish_parasite_fields(target['mqtt_path'], {
                    "ai_person": counts.get('person', 0),
                    "ai_car": counts.get('car', 0),
                    "ai_dog": counts.get('dog', 0),
                    "ai_last_detection": datetime.now().isoformat()
                })

        return own_state
```

### Example 2: Notification Layer for Any Device

```python
class Connector(BaseConnector):
    """Universal notification parasite - works with any device type"""

    def initialize_connection(self):
        self.telegram_bot = TelegramBot(token=self.config['telegram_token'])
        self.last_notifications = {}

    def get_device_state(self, device_id, device_config):
        own_state = {"online": True, "sent_count": len(self.last_notifications)}

        for target in self.parasite_targets:
            if target['device_id'] == device_id:
                parent_state = self.get_parent_state(target['mqtt_path'])

                if parent_state:
                    # Check configured trigger conditions
                    should_notify = self._check_trigger(parent_state, device_config)

                    if should_notify:
                        self._send_notification(device_id, parent_state)

                        # Publish notification metadata
                        self.publish_parasite_fields(target['mqtt_path'], {
                            "notification_last_sent": datetime.now().isoformat(),
                            "notification_count": len(self.last_notifications)
                        })

        return own_state
```

## Debugging and Troubleshooting

### Monitoring Parasite Connections

Check `/parasite` registry to see which parents a connector extends:
```bash
mosquitto_sub -t 'iot2mqtt/v1/instances/+/devices/+/parasite' -v
```

### Verifying Field Publication

Monitor parent device state fields:
```bash
mosquitto_sub -t 'iot2mqtt/v1/instances/cameras_abc/devices/camera_1/state/#' -v
```

### Testing CMD Independence

Verify parasitic connector responds to its own CMD, not parent CMD:
```bash
# This should trigger parasitic connector
mosquitto_pub -t 'iot2mqtt/v1/instances/motion_xyz/devices/camera_1/cmd' \
  -m '{"sensitivity": 0.9}'

# This should NOT affect parasitic connector
mosquitto_pub -t 'iot2mqtt/v1/instances/cameras_abc/devices/camera_1/cmd' \
  -m '{"zoom": 2.0}'
```

### Common Issues

**Issue: Parasite fields not appearing on parent device**
- Check `/parasite` registry exists
- Verify device_id matches exactly between parasite and parent
- Check MQTT logs for "Published N parasite field(s)" messages
- Verify parent device is online and publishing state

**Issue: Parent state always None in get_parent_state()**
- Wait 2-3 seconds after startup for parent state subscription
- Check parent device is actively publishing (not offline)
- Verify mqtt_path in parasite_targets is correct
- Check logs for "Subscribed to parent device" messages

**Issue: Commands sent to parent CMD affecting parasite**
- This should NEVER happen - it indicates bug in implementation
- Verify connector uses `self.instance_id` not parent instance_id
- Check BaseConnector._setup_subscriptions() subscribes to correct instance

**Issue: Parasite stops when parent restarts**
- Parasites should continue running when parent restarts
- Parent state cache will be empty until parent comes back online
- Use `get_parent_state()` with None-checking
- Consider implementing reconnection logic in initialize_connection()
