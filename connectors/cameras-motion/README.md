# Camera Motion Detection 🎬

**Parasitic connector that adds FFmpeg-based motion detection to IP cameras**

## Overview

The Camera Motion Detection connector is a **parasitic connector** that extends your existing camera devices with real-time motion detection capabilities. It analyzes RTSP streams using FFmpeg and publishes motion events directly to parent camera MQTT topics, creating a seamless integration without modifying your camera connector.

### Key Features

- ⚡ **Fast & Efficient** - FFmpeg-based detection, low CPU usage
- 📈 **Massive Scale** - Supports up to 100 cameras in a single instance
- 🎛️ **Real-time Control** - Adjust sensitivity via MQTT commands
- 🔌 **Parasitic Architecture** - Extends cameras without modification
- 🌐 **Multi-Instance** - Monitor cameras from different camera instances
- 🎯 **Independent Control** - Separate CMD topics for each component

## Architecture

### Parasitic Connector Pattern

This connector uses IoT2MQTT's parasitic connector architecture:

1. **Parent Devices**: Existing cameras from `cameras` connector
2. **Extension Fields**: Publishes `motion`, `motion_confidence`, `motion_last_detected` to parent camera state
3. **Independent Control**: Own CMD topics at `iot2mqtt/v1/instances/cameras_motion_xyz/devices/{device_id}/cmd`
4. **Dual-Topic Publishing**: Publishes both own operational state and parent device extensions

### MQTT Topic Structure

**Parasitic Connector (Own State):**
```
iot2mqtt/v1/instances/cameras_motion_abc123/devices/camera_1/state
→ {"online": true, "status": "detecting", "frames_analyzed": 1234, "errors": 0}

iot2mqtt/v1/instances/cameras_motion_abc123/devices/camera_1/cmd
← Accepts: {"sensitivity": 0.8, "enabled": true, "reset_stats": true}
```

**Parent Camera (Extended Fields):**
```
iot2mqtt/v1/instances/cameras_xyz/devices/camera_1/state/motion → true
iot2mqtt/v1/instances/cameras_xyz/devices/camera_1/state/motion_confidence → 0.85
iot2mqtt/v1/instances/cameras_xyz/devices/camera_1/state/motion_last_detected → "2025-10-23T..."
```

## Installation

### Requirements

- Docker and Docker Compose
- At least one `cameras` connector instance with RTSP-enabled cameras
- FFmpeg (installed automatically in container)

### Setup via Web UI

1. Navigate to **Integrations** → **Add Integration**
2. Select **Camera Motion Detection**
3. Click **Add Motion Detection**
4. Select camera(s) to monitor:
   - Search by name, IP, or brand
   - Click **Add Another Camera** to monitor multiple cameras
5. Configure motion detection settings:
   - **Sensitivity**: 0.1 (very sensitive) to 1.0 (less sensitive)
   - **Check Interval**: How often to analyze frames (seconds)
6. Set instance name and update interval
7. Click **Create Instance**

### Multi-Camera Setup

The connector supports adding up to **100 cameras** from multiple camera instances:

1. Add first camera → Configure settings
2. Click **Add Another Camera** button
3. Repeat for each camera you want to monitor
4. All cameras will be managed by a single motion detection instance

**Example Configuration:**
```
Cameras from different instances:
- IoT2mqtt/v1/instances/cameras_main/devices/front_door
- IoT2mqtt/v1/instances/cameras_main/devices/back_door
- IoT2mqtt/v1/instances/cameras_garage/devices/driveway
- IoT2mqtt/v1/instances/cameras_office/devices/entrance
```

## Motion Detection

### How It Works

1. **RTSP Stream Analysis**: Connects to camera RTSP streams
2. **FFmpeg Scene Detection**: Uses `select='gt(scene,X)'` filter for frame-to-frame changes
3. **Motion Events**: Detects significant changes between consecutive frames
4. **MQTT Publishing**: Publishes motion state to parent camera topics every update interval

### Sensitivity Configuration

Sensitivity controls how much change is needed to trigger motion:

| Value | Behavior | Use Case |
|-------|----------|----------|
| 0.1 | Very sensitive | Detect small movements, indoor cameras |
| 0.3 | Sensitive | General purpose, moderate activity areas |
| 0.5 | Moderate | Outdoor cameras, some environmental changes |
| 0.7 | **Default** | Balanced detection, ignore minor changes |
| 1.0 | Less sensitive | Only detect major movements, reduce false positives |

## Commands

Control motion detection via MQTT CMD topics:

### Adjust Sensitivity
```bash
mosquitto_pub -t 'iot2mqtt/v1/instances/cameras_motion_abc/devices/camera_1/cmd' \
  -m '{"sensitivity": 0.5}'
```

### Enable/Disable Detection
```bash
# Disable (pause without removing)
mosquitto_pub -t 'iot2mqtt/v1/instances/cameras_motion_abc/devices/camera_1/cmd' \
  -m '{"enabled": false}'

# Re-enable
mosquitto_pub -t 'iot2mqtt/v1/instances/cameras_motion_abc/devices/camera_1/cmd' \
  -m '{"enabled": true}'
```

### Reset Statistics
```bash
mosquitto_pub -t 'iot2mqtt/v1/instances/cameras_motion_abc/devices/camera_1/cmd' \
  -m '{"reset_stats": true}'
```

## Published Fields

### Own Instance State

Published to: `iot2mqtt/v1/instances/cameras_motion_xyz/devices/{device_id}/state`

| Field | Type | Description |
|-------|------|-------------|
| `online` | boolean | Connector operational status |
| `status` | string | "detecting" or "paused" |
| `frames_analyzed` | integer | Total frames analyzed since start |
| `errors` | integer | Error count (connection issues, etc.) |
| `last_update` | ISO 8601 | Last state update timestamp |

### Parent Camera Extension

Published to: `iot2mqtt/v1/instances/cameras_xyz/devices/{device_id}/state/`

| Field | Type | Description |
|-------|------|-------------|
| `motion` | boolean | Is motion currently detected? |
| `motion_confidence` | float | Confidence level (0.0 - 1.0) |
| `motion_last_detected` | ISO 8601 | Timestamp of last motion event |

## Performance

### Resource Usage

**Per Camera:**
- CPU: ~2-5% (FFmpeg subprocess)
- RAM: ~50-100 MB per stream
- Network: Minimal (reads RTSP, publishes small MQTT messages)

**100 Camera Instance:**
- CPU: ~200-500% (multi-core utilization)
- RAM: ~5-10 GB
- Recommended: 8+ CPU cores, 16 GB RAM

### Optimization Tips

1. **Increase Check Interval**: Set to 2-5 seconds for less CPU usage
2. **Adjust Sensitivity**: Higher values = less processing
3. **Disable Unused Cameras**: Use `enabled: false` command
4. **Use Instance Filtering**: Create separate instances for different camera groups

## Troubleshooting

### No Motion Detected

**Check RTSP URL:**
```bash
# Verify parent camera has RTSP stream
mosquitto_sub -t 'iot2mqtt/v1/instances/cameras_xyz/devices/camera_1/state' -C 1
# Look for: "stream_urls": {"rtsp": "rtsp://..."}
```

**Check Motion Detector Logs:**
```bash
docker logs -f iot2mqtt_cameras_motion_abc123
```

**Test FFmpeg Manually:**
```bash
ffmpeg -i rtsp://camera_ip/stream -vf "select='gt(scene,0.7)'" -f null -
```

### High CPU Usage

- Increase `check_interval` to 2-5 seconds
- Increase `sensitivity` to reduce detection frequency
- Reduce number of cameras per instance (split into multiple instances)

### Motion Detection Too Sensitive

- Increase `sensitivity` value (0.8 - 1.0)
- Check for:
  - Moving trees/shadows (outdoor cameras)
  - Lighting changes
  - Camera shake/vibration

### Motion Detection Not Sensitive Enough

- Decrease `sensitivity` value (0.1 - 0.3)
- Verify RTSP stream quality (low FPS = missed motion)
- Check camera positioning (motion in detection area?)

### Camera Goes Offline

Motion detector handles offline cameras gracefully:
- Error count increases in state
- Reconnects automatically when camera comes back
- Other cameras continue working normally

## Example Use Cases

### Home Security System

Monitor all entry points with motion detection:
```
Cameras monitored:
- Front door (sensitivity: 0.5)
- Back door (sensitivity: 0.5)
- Garage (sensitivity: 0.7)
- Windows (sensitivity: 0.3)
```

Trigger automation when motion detected at any door.

### Office Occupancy Detection

Track office space usage:
```
Cameras monitored:
- Conference room (sensitivity: 0.6)
- Reception area (sensitivity: 0.5)
- Parking lot (sensitivity: 0.8)
```

Log occupancy patterns, send notifications when areas become active.

### Wildlife Monitoring

Detect animals near outdoor cameras:
```
Cameras monitored:
- Bird feeder (sensitivity: 0.3)
- Backyard (sensitivity: 0.4)
- Trail camera (sensitivity: 0.5)
```

Capture motion timestamps for wildlife activity analysis.

## Integration with Other Connectors

### Chaining Parasitic Connectors

Motion detection can trigger other parasitic connectors:

```
cameras → cameras-motion → cameras-recorder
                        ↘ cameras-telegram
```

Example workflow:
1. `cameras-motion` detects motion
2. `cameras-recorder` starts recording when `motion: true`
3. `cameras-telegram` sends notification with snapshot

### Home Assistant

Motion fields appear automatically in Home Assistant:
```yaml
binary_sensor:
  - platform: mqtt
    state_topic: "iot2mqtt/v1/instances/cameras_xyz/devices/front_door/state/motion"
    device_class: motion

sensor:
  - platform: mqtt
    state_topic: "iot2mqtt/v1/instances/cameras_xyz/devices/front_door/state/motion_confidence"
    unit_of_measurement: "%"
```

## Development

### File Structure
```
connectors/cameras-motion/
├── connector.py          # Main connector logic
├── motion_detector.py    # FFmpeg motion detection engine
├── setup.json            # Web UI setup flow
├── Dockerfile            # Container definition
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

### Testing Locally

```bash
# Build container
docker build -t iot2mqtt/cameras-motion connectors/cameras-motion/

# Run with test config
docker run --rm -it \
  -e INSTANCE_NAME=cameras_motion_test \
  -e MQTT_HOST=localhost \
  -v ./instances:/app/instances \
  -v ./shared:/app/shared \
  iot2mqtt/cameras-motion
```

## Support

- **Documentation**: [IoT2MQTT Parasitic Connectors Guide](../../docs/parasitic-connectors.md)
- **Issues**: [GitHub Issues](https://github.com/eduard256/IoT2mqtt/issues)
- **Discussions**: [GitHub Discussions](https://github.com/eduard256/IoT2mqtt/discussions)

## License

MIT License - see [LICENSE](../../LICENSE) file

---

**Made with ❤️ for the IoT2MQTT Community**
