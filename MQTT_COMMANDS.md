# IoT2MQTT Command Standardization v2.0

## Overview

This document defines the standardized MQTT command payloads for IoT2MQTT system. All connectors and devices MUST follow these standards to ensure compatibility across the ecosystem.

## Core Principles

- **Simple for basic usage** - Common commands are straightforward
- **Powerful when needed** - Advanced features available but optional
- **MQTT for control only** - Media content delivered via URLs, not MQTT
- **Universal compatibility** - Works with any IoT device type

## Command Structure

All commands are sent to topic: `{base_topic}/v1/instances/{instance_id}/devices/{device_id}/cmd`

### Base Command Format

```json
{
  "id": "cmd_unique_id",
  "timestamp": "2024-01-15T10:30:00.123Z",
  "values": {
    // Command specific values
  },
  "timeout": 5000,      // Optional, in milliseconds
  "priority": "normal", // Optional: high, normal, low
  "transition": 2000    // Optional: smooth transition in ms
}
```

## Standard Commands

### 1. Power Control

#### Turn On/Off
```json
{
  "values": {
    "power": true  // true = on, false = off
  }
}
```

#### Toggle Power
```json
{
  "values": {
    "power": "toggle"
  }
}
```

### 2. Brightness Control

#### Absolute Brightness (0-100%)
```json
{
  "values": {
    "brightness": 75  // 0-100
  }
}
```

#### Relative Brightness
```json
{
  "values": {
    "brightness": "+10"  // Increase by 10%
  }
}

// Alternative method
{
  "values": {
    "brightness_step": -10  // Decrease by 10%
  }
}
```

### 3. Color Control

The system supports THREE popular color formats. Connectors auto-detect the format:

#### RGB Format
```json
{
  "values": {
    "color": {
      "r": 255,
      "g": 128,
      "b": 0
    }
  }
}
```

#### HEX Format
```json
{
  "values": {
    "color": "#FF8000"
  }
}
```

#### HSV Format
```json
{
  "values": {
    "color": {
      "h": 180,  // Hue: 0-360
      "s": 100,  // Saturation: 0-100
      "v": 100   // Value/Brightness: 0-100
    }
  }
}
```

#### Color Temperature (separate from color)
```json
{
  "values": {
    "color_temp": 4000  // Kelvin (2700-6500 typical)
  }
}
```

### 4. Smooth Transitions

Add `transition` to any command for smooth changes:

```json
{
  "values": {
    "brightness": 100,
    "color": "#FF0000",
    "transition": 2000  // 2 seconds smooth transition
  }
}
```

### 5. Temperature Control

#### Set Target Temperature
```json
{
  "values": {
    "target_temp": 22.5  // Celsius
  }
}
```

### 6. Mode Control

#### Set Operation Mode
```json
{
  "values": {
    "mode": "auto"  // Options: auto, manual, eco, comfort, sleep, etc.
  }
}
```

#### Fan Mode
```json
{
  "values": {
    "fan_mode": "medium"  // Options: auto, low, medium, high, turbo
  }
}
```

### 7. Speed Control

#### Absolute Speed
```json
{
  "values": {
    "speed": 50  // 0-100
  }
}
```

#### Relative Speed
```json
{
  "values": {
    "speed": "+10"  // Increase by 10%
  }
}
```

### 8. Position Control

#### Set Position (Blinds, Curtains)
```json
{
  "values": {
    "position": 75  // 0=closed, 100=open
  }
}
```

#### Relative Position
```json
{
  "values": {
    "position": "-25"  // Close by 25%
  }
}
```

### 9. Volume Control

#### Set Volume
```json
{
  "values": {
    "volume": 30  // 0-100
  }
}
```

#### Mute/Unmute
```json
{
  "values": {
    "mute": true  // true/false or "toggle"
  }
}
```

### 10. Lock Control

#### Lock/Unlock
```json
{
  "values": {
    "lock": true  // true=locked, false=unlocked, "toggle"
  }
}
```

#### With PIN Code
```json
{
  "values": {
    "lock": false,
    "pin": "1234"
  }
}
```

### 11. Scene & Effects

#### Activate Scene
```json
{
  "values": {
    "scene": "movie_night"
  }
}
```

#### Activate Effect
```json
{
  "values": {
    "effect": "rainbow",
    "effect_speed": 50  // Optional: 0-100
  }
}
```

### 12. Timer Control

#### Simple Timer (auto-off)
```json
{
  "values": {
    "timer": 3600  // Seconds until auto-off
  }
}
```

### 13. Media Control

#### Playback Control
```json
{
  "values": {
    "media": "play"  // play, pause, stop, next, previous
  }
}
```

#### Set Source
```json
{
  "values": {
    "source": "hdmi1"
  }
}
```

### 14. Vacuum Control

#### Basic Commands
```json
{
  "values": {
    "vacuum": "start"  // start, stop, pause, dock, spot
  }
}
```

#### Vacuum Mode
```json
{
  "values": {
    "vacuum_mode": "quiet"  // quiet, standard, medium, turbo
  }
}
```

## Advanced Commands

### 1. Execute Commands (SSH/Scripts)

```json
{
  "values": {
    "exec": "sudo systemctl restart nginx",
    "exec_timeout": 30000  // Optional, default 5000ms
  }
}
```

Response:
```json
{
  "cmd_id": "cmd_123",
  "status": "success",
  "output": "nginx restarted successfully",
  "exit_code": 0
}
```

### 2. Sequence Commands

Execute multiple commands in order with delays:

```json
{
  "values": {
    "sequence": [
      {"power": true, "delay": 1000},
      {"brightness": 50, "transition": 2000},
      {"color": "#FF0000", "delay": 500},
      {"effect": "pulse"}
    ]
  }
}
```

### 3. Query State

```json
{
  "values": {
    "query": ["power", "brightness", "color"],  // Specific properties
    "subscribe": 5000  // Optional: subscribe for updates every 5s
  }
}
```

### 4. Presets

#### Save Current State
```json
{
  "values": {
    "save_preset": "evening"
  }
}
```

#### Restore Preset
```json
{
  "values": {
    "preset": "evening"
  }
}
```

### 5. Notifications

```json
{
  "values": {
    "notify": "flash",  // flash, beep, pulse
    "notify_duration": 3000,
    "notify_color": "#FF0000"  // For RGB devices
  }
}
```

### 6. Raw Commands

For direct device communication:

```json
{
  "values": {
    "raw": "SET_POWER 1",
    "raw_protocol": "tcp"  // tcp, udp, serial
  }
}
```

## Media Commands

Media content is ALWAYS delivered via URLs, never embedded in MQTT messages.

### 1. Camera Snapshot

Request:
```json
{
  "values": {
    "snapshot": {
      "quality": 90,      // 1-100
      "resolution": "1080p"  // 1080p, 720p, max, thumbnail
    }
  }
}
```

Response:
```json
{
  "cmd_id": "cmd_123",
  "status": "success",
  "media": {
    "type": "image/jpeg",
    "url": "http://192.168.1.100:8080/snapshot/abc123.jpg",
    "size": 245632,
    "expires": "2024-01-15T10:35:00Z"  // URL expiry time
  }
}
```

### 2. Video Stream

Request:
```json
{
  "values": {
    "stream": {
      "action": "start",  // start, stop
      "quality": "1080p",
      "protocol": "rtsp"  // rtsp, webrtc, hls, mjpeg
    }
  }
}
```

Response:
```json
{
  "cmd_id": "cmd_123",
  "status": "success",
  "stream": {
    "protocol": "rtsp",
    "url": "rtsp://192.168.1.100:554/stream1",
    "auth": {
      "username": "viewer",
      "password": "temp_pass_123"
    },
    "expires": "2024-01-15T11:00:00Z"
  }
}
```

### 3. Video Recording

Request:
```json
{
  "values": {
    "record": {
      "duration": 30,  // seconds
      "quality": "1080p"
    }
  }
}
```

Immediate Response:
```json
{
  "cmd_id": "cmd_123",
  "status": "recording",
  "record_id": "rec_456"
}
```

Event (published later):
```json
{
  "event": "record_complete",
  "record_id": "rec_456",
  "media": {
    "type": "video/mp4",
    "url": "http://192.168.1.100:8080/recordings/rec_456.mp4",
    "duration": 30,
    "size": 15728640,
    "expires": "2024-01-15T10:40:00Z"
  }
}
```

### 4. Audio Commands

#### Text-to-Speech
```json
{
  "values": {
    "speak": {
      "text": "Hello, World!",
      "language": "en-US",
      "voice": "female"
    }
  }
}
```

#### Play Audio
```json
{
  "values": {
    "play": {
      "url": "http://example.com/sound.mp3",
      "volume": 80
    }
  }
}
```

### 5. Display Commands

```json
{
  "values": {
    "display": {
      "text": "Temperature: 22°C",
      "duration": 5000,
      "scroll": false
    }
  }
}

// Or with image URL
{
  "values": {
    "display": {
      "type": "image",
      "url": "http://example.com/chart.png",
      "duration": 10000
    }
  }
}
```

## Special Commands

### 1. Reboot Device
```json
{
  "values": {
    "reboot": true,
    "confirm": true  // Safety confirmation
  }
}
```

### 2. Reset to Defaults
```json
{
  "values": {
    "reset": "factory",  // factory, settings, network
    "confirm": true
  }
}
```

### 3. Calibrate Sensor
```json
{
  "values": {
    "calibrate": {
      "sensor": "temperature",
      "offset": -0.5
    }
  }
}
```

## Response Format

Responses are published to: `{base_topic}/v1/instances/{instance_id}/devices/{device_id}/cmd/response`

### Success Response
```json
{
  "cmd_id": "cmd_123",
  "status": "success",
  "timestamp": "2024-01-15T10:30:00.456Z",
  "result": {
    // Optional result data
  }
}
```

### Error Response
```json
{
  "cmd_id": "cmd_123",
  "status": "error",
  "timestamp": "2024-01-15T10:30:00.456Z",
  "error": {
    "code": "DEVICE_OFFLINE",
    "message": "Device is not responding"
  }
}
```

## Device Capabilities

Devices should publish their capabilities to: `{base_topic}/v1/instances/{instance_id}/devices/{device_id}/capabilities`

```json
{
  "api_version": "2.0",
  "supports": [
    "power",
    "brightness",
    "color",
    "color_temp",
    "transition",
    "effects"
  ],
  "features": {
    "color_formats": ["rgb", "hex", "hsv"],
    "transition": true,
    "relative_changes": true,
    "presets": 10,
    "sequences": true
  },
  "ranges": {
    "brightness": [0, 100],
    "color_temp": [2700, 6500],
    "transition": [0, 10000]
  },
  "effects": ["none", "rainbow", "pulse", "fade", "disco"],
  "scenes": ["movie", "reading", "night", "party"],
  "media": {
    "snapshot": {
      "formats": ["jpeg", "png"],
      "max_resolution": "1920x1080",
      "delivery": "url"  // Always URL, never inline
    },
    "stream": {
      "protocols": ["rtsp", "webrtc", "hls"],
      "resolutions": ["1080p", "720p", "480p"]
    }
  },
  "limits": {
    "command_rate": 10,  // Commands per second
    "url_expiry": 300    // URL validity in seconds
  }
}
```

## Examples for Common Devices

### Smart Bulb
```json
{
  "values": {
    "power": true,
    "brightness": 75,
    "color": "#FFA500",
    "transition": 1000
  }
}
```

### Thermostat
```json
{
  "values": {
    "mode": "heat",
    "target_temp": 21,
    "fan_mode": "auto"
  }
}
```

### Smart Lock
```json
{
  "values": {
    "lock": false,
    "pin": "1234"
  }
}
```

### Camera
```json
{
  "values": {
    "snapshot": {
      "quality": 90
    }
  }
}
```

### Smart Curtains
```json
{
  "values": {
    "position": 50,
    "transition": 5000
  }
}
```

## Implementation Notes

1. **Color Format Detection**: Connectors must auto-detect color format:
   - String starting with '#' = HEX
   - Object with 'r', 'g', 'b' = RGB
   - Object with 'h', 's', 'v' = HSV

2. **Relative Changes**: Any numeric value as string with '+' or '-' prefix is relative

3. **Transition Support**: The `transition` parameter applies to ALL value changes in the command

4. **Media Delivery**: NEVER embed binary data in MQTT. Always use URLs with expiry times

5. **Command Priority**: 
   - High: Safety commands (lock, alarm)
   - Normal: User interactions
   - Low: Telemetry, queries

6. **Error Handling**: Unknown commands should be logged but not cause connector crashes

7. **Backwards Compatibility**: Support both old format (if any) and new format during transition

## Validation Rules

1. **Numeric ranges** must be validated:
   - Percentages: 0-100
   - RGB: 0-255
   - HSV: H:0-360, S:0-100, V:0-100
   - Temperature: Device specific

2. **String commands** are case-insensitive

3. **Timestamps** must be ISO 8601 format

4. **URLs** must include expiry time for security

5. **Transitions** capped at device maximum (typically 10 seconds)

---

*Version: 2.0 | Last Updated: 2024-01-15*