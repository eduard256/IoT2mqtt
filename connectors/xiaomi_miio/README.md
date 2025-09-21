# Xiaomi MiIO Connector for IoT2MQTT

Complete integration for ALL Xiaomi MiIO devices, providing full feature parity with Home Assistant's xiaomi_miio integration.

## Features

- **Complete Device Support**: Supports ALL 273+ Xiaomi MiIO device models
- **Full Protocol Implementation**: Native MiIO protocol with encryption
- **Cloud Integration**: Optional Xiaomi cloud support for token retrieval
- **Auto Discovery**: Automatic device discovery via mDNS and network scanning
- **Advanced Features**: Zone cleaning, segments, remote control, consumables tracking
- **Real-time Updates**: Coordinated polling with configurable intervals
- **Error Handling**: Automatic retry on network issues (-9999 errors)

## Supported Device Categories

### Vacuum Cleaners
- All Roborock models (S4, S5, S6, S7 series)
- Xiaomi Mi Robot Vacuum (V1, V2)
- Zone cleaning, segment cleaning, remote control
- Consumables tracking, timers, DND settings

### Air Purifiers
- Xiaomi Mi Air Purifier (1, 2S, 3H, Pro, 4 series)
- Zhimi Air Purifier models
- AQI monitoring, filter tracking, favorite levels
- LED control, child lock, buzzer settings

### Fans
- Smartmi Standing Fan series
- Dmaker Fan models (P5, P9, P10, P11, P18)
- Oscillation control, natural mode, ionizer
- Speed presets, delay-off timer

### Humidifiers
- Xiaomi Mi Humidifier series
- Deerma Humidifier models
- Target humidity control, dry mode
- Water level monitoring

### Lights
- Philips Smart Bulbs
- Xiaomi Desk Lamps
- Ceiling Lights
- Color control (RGB, HSV, temperature)
- Scenes and effects

### Smart Plugs & Switches
- Chuangmi Smart Plugs
- Power Strips
- Power monitoring, WiFi LED control

### Gateways
- Lumi Gateway
- Sub-device management
- Illumination control

## Installation

### Docker

```bash
docker build -t iot2mqtt-xiaomi-miio connectors/xiaomi_miio/
docker run -d \
  --name xiaomi-connector \
  -v ./instances:/app/instances \
  -e INSTANCE_NAME=xiaomi_home \
  -e MQTT_HOST=localhost \
  -e MQTT_PORT=1883 \
  iot2mqtt-xiaomi-miio
```

### Manual

```bash
pip install -r connectors/xiaomi_miio/requirements.txt
python -m connectors.xiaomi_miio.connector
```

## Configuration

### Basic Configuration

```json
{
  "instance_id": "xiaomi_home",
  "connector_type": "xiaomi_miio",
  "discovery_enabled": true,
  "devices": [
    {
      "device_id": "vacuum_living",
      "host": "192.168.1.100",
      "token": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      "model": "roborock.vacuum.s5"
    }
  ]
}
```

### Cloud Integration

```json
{
  "cloud_credentials": {
    "username": "your_xiaomi_account",
    "password": "your_password",
    "country": "cn"
  }
}
```

Country codes: `cn`, `de`, `i2`, `ru`, `sg`, `us`

## Getting Device Tokens

### Method 1: Xiaomi Cloud (Easiest)
1. Configure cloud credentials in the connector
2. Devices will be discovered automatically with tokens

### Method 2: Modified Mi Home App
1. Use modified Mi Home app version 5.4.49
2. Go to Device Settings > Network Info
3. Token will be displayed

### Method 3: Backup Extraction
1. Enable developer mode on Android
2. Backup Mi Home app: `adb backup -noapk com.xiaomi.smarthome`
3. Extract token from backup database

### Method 4: Packet Sniffing
1. Reset device to factory settings
2. Sniff packets during setup
3. Extract token from handshake

## MQTT Commands

### Standard Commands

All devices support IoT2MQTT standard commands:

```json
{
  "values": {
    "power": true,
    "brightness": 75,
    "color": "#FF0000",
    "mode": "auto"
  }
}
```

### Device-Specific Commands

#### Vacuum Commands

```json
{
  "values": {
    "vacuum": "start",
    "clean_zone": {
      "zone": [25500, 25500, 29000, 29000],
      "repeats": 2
    },
    "clean_segment": [16, 17, 18],
    "fan_speed": "Medium"
  }
}
```

#### Air Purifier Commands

```json
{
  "values": {
    "mode": "Auto",
    "favorite_level": 10,
    "child_lock": true,
    "led_brightness": 50
  }
}
```

#### Fan Commands

```json
{
  "values": {
    "speed": 50,
    "oscillation": true,
    "oscillation_angle": 120,
    "natural_mode": true,
    "timer": 3600
  }
}
```

## State Topics

States are published to: `IoT2mqtt/v1/instances/{instance_id}/devices/{device_id}/state`

Example vacuum state:
```json
{
  "online": true,
  "power": true,
  "activity": "Cleaning",
  "battery": 85,
  "fan_speed": 60,
  "error": null,
  "consumables": {
    "main_brush": 280,
    "main_brush_left": 20,
    "side_brush": 180,
    "side_brush_left": 20,
    "filter": 140,
    "filter_left": 10
  }
}
```

## Advanced Features

### Zone Cleaning (Vacuums)

Define cleaning zones with coordinates:
```json
{
  "values": {
    "clean_zone": {
      "zone": [x1, y1, x2, y2],
      "repeats": 2
    }
  }
}
```

### Segment Cleaning (Vacuums)

Clean specific rooms by segment ID:
```json
{
  "values": {
    "clean_segment": [16, 17, 18]
  }
}
```

### Remote Control (Vacuums)

Manual control mode:
```json
{
  "values": {
    "remote_control": {
      "action": "start"
    }
  }
}

{
  "values": {
    "remote_control": {
      "action": "move",
      "velocity": 0.3,
      "rotation": 45,
      "duration": 1500
    }
  }
}
```

### Favorite Levels (Purifiers)

Set custom fan speeds:
```json
{
  "values": {
    "favorite_level": 14
  }
}
```

### Scenes (Lights)

Activate predefined scenes:
```json
{
  "values": {
    "scene": "sunrise"
  }
}
```

## Troubleshooting

### Device Not Responding

1. Verify token is correct (32 characters)
2. Check device IP is reachable
3. Ensure device firmware is up to date
4. Try power cycling the device

### Token Invalid

1. Token may have changed after factory reset
2. Use cloud integration to get updated token
3. Re-pair device with Mi Home app

### Discovery Not Working

1. Ensure devices are on same network
2. Check firewall rules for UDP port 54321
3. Enable mDNS/Bonjour on network

### Error -9999

This is a network timeout error. The connector automatically retries once. If persistent:
1. Check network stability
2. Reduce polling frequency
3. Check if device is overloaded

## Model List

See `device_registry.py` for the complete list of 273+ supported models.

## Development

### Adding New Models

1. Add model constant to `device_registry.py`
2. Map model to device class
3. Define feature flags
4. Test with actual device

### Protocol Details

The MiIO protocol uses:
- UDP port 54321
- AES-128-CBC encryption
- MD5 checksums
- Token-based authentication

## Credits

This connector implements full compatibility with Home Assistant's xiaomi_miio integration, supporting all device types and features.