# HomeKit Connector for IoT2mqtt

Control HomeKit accessories via MQTT using Apple's HomeKit Accessory Protocol (HAP).

## Features

- **Real-time Events**: Instant push notifications when device state changes
- **Auto-Discovery**: Automatically find HomeKit accessories on your network via mDNS/Zeroconf
- **Secure Pairing**: Industry-standard HAP pairing with encrypted communication
- **Wide Device Support**: Lights, switches, thermostats, locks, sensors, and more
- **asyncio Architecture**: Efficient event-driven communication with HomeKit devices
- **Home Assistant Integration**: Automatic MQTT discovery for seamless HA integration

## Supported Devices

- **Lights**: Brightness, color (RGB/HSV), color temperature
- **Switches**: On/off control
- **Thermostats**: Temperature, mode control
- **Locks**: Lock/unlock control
- **Sensors**: Motion, contact, temperature, humidity, battery
- **Covers**: Blinds, shades, garage doors
- **Fans**: Speed control
- **Outlets**: Power control

Compatible with brands: Eve, Philips Hue, Nanoleaf, LIFX, Aqara, and any HAP-compatible device.

## Architecture

### Level 1 (Single Process)
- Single Python 3.11 process with asyncio event loop
- Uses `aiohomekit==3.2.20` (same library as Home Assistant)
- Hybrid asyncio + threading architecture to bridge HAP (asyncio) with MQTT (threading)

### Components

1. **connector.py**: Main connector implementing BaseConnector interface
2. **homekit_manager.py**: Wrapper around aiohomekit for device management
3. **main.py**: Entry point
4. **actions/**: Setup flow tools (discovery, pairing, validation)

## How It Works

### Initialization
```
1. Load configuration from /app/instances/{instance_id}.json
2. Load pairing data from /run/secrets/{instance_id}_creds (encrypted)
3. Start asyncio event loop in background thread
4. Initialize aiohomekit Controller
5. Connect to all configured devices
6. Subscribe to characteristic change events
```

### Event Flow (Real-time)
```
HomeKit Characteristic Changes
    ↓
aiohomekit Event Callback (asyncio thread)
    ↓
Update Internal State Cache
    ↓
Publish to MQTT (thread-safe)
    ↓
MQTT Broker
```

### Command Flow
```
MQTT Command → {BASE}/devices/{device_id}/cmd
    ↓
BaseConnector._handle_command() (MQTT thread)
    ↓
connector.set_device_state() (sync wrapper)
    ↓
asyncio.run_coroutine_threadsafe()
    ↓
homekit_manager.set_state() (asyncio context)
    ↓
aiohomekit pairing.put_characteristics()
    ↓
HomeKit Device Executes Command
    ↓
Event Callback → MQTT State Update
```

### Polling (Backup)
```
BaseConnector._main_loop() every update_interval
    ↓
connector.get_device_state()
    ↓
Return cached state (from events) OR query device
    ↓
Publish to MQTT if changed
```

## Configuration

### Instance Config (`instances/homekit/{instance_id}.json`)
```json
{
  "instance_id": "homekit_abc123",
  "connector_type": "homekit",
  "friendly_name": "My HomeKit Bridge",
  "enabled": true,
  "update_interval": 30,
  "ha_discovery_enabled": true,
  "devices": [
    {
      "device_id": "living_room_light",
      "name": "Living Room Light",
      "model": "Hue Color Bulb",
      "category": "lightbulb",
      "pairing_id": "AA:BB:CC:DD:EE:FF",
      "ip": "192.168.1.100",
      "port": 5001,
      "enabled": true
    }
  ]
}
```

### Secrets (`secrets/instances/{instance_id}.secret`)
```json
{
  "pairings": {
    "living_room_light": {
      "AccessoryPairingID": "...",
      "AccessoryLTPK": "...",
      "iOSDevicePairingID": "...",
      "iOSDeviceLTSK": "...",
      "iOSDeviceLTPK": "...",
      "AccessoryIP": "192.168.1.100",
      "AccessoryPort": 5001
    }
  }
}
```

## MQTT Topics

### Commands (Subscribe)
```
{BASE}/devices/{device_id}/cmd
```

Example commands:
```json
# Turn on light
{"on": true}

# Set brightness
{"brightness": 80}

# Set color (RGB)
{"hue": 120, "saturation": 75}

# Set color temperature
{"color_temperature": 500}

# Lock door
{"lock_target": 1}
```

### State (Publish)
```
{BASE}/devices/{device_id}/state
```

Example state:
```json
{
  "online": true,
  "on": true,
  "brightness": 80,
  "hue": 120,
  "saturation": 75,
  "last_update": "2025-10-24T12:00:00.000Z"
}
```

### Status (Publish)
```
{BASE}/status → "online" | "offline" (LWT)
```

## Setup Flow

### Auto Discovery Flow
1. **Instance Name**: Give the connector a name
2. **Discovery**: Automatically scan network for HomeKit accessories (15s timeout)
3. **Select Device**: Choose accessory from list
4. **Enter PIN**: Enter 8-digit PIN code (XXX-XX-XXX format)
5. **Pairing**: Connect and pair with accessory
6. **Configure**: Set device name
7. **Complete**: Instance created with pairing data saved to secrets

### Manual Entry Flow
1. **Instance Name**: Give the connector a name
2. **Device Info**: Enter name, IP, port, and PIN manually
3. **Pairing**: Connect and pair with accessory
4. **Complete**: Instance created

## Troubleshooting

### Discovery Finds No Devices
- Ensure devices are unpaired (not connected to another HomeKit controller)
- Check network connectivity (must be on same subnet)
- Verify mDNS/Bonjour is not blocked by firewall
- Some devices may not advertise when paired

### Pairing Fails
- Double-check PIN code (format: XXX-XX-XXX)
- Ensure device is in pairing mode
- Verify device is not already paired with another controller
- Check IP address is correct and device is reachable

### Device Goes Offline
- Check network connectivity
- Verify device is powered on
- Re-pairing may be required if device was reset
- Check Docker container logs for errors

### Events Not Working
- Events are automatic with aiohomekit
- If polling only, check update_interval in config
- Verify device supports event notifications

## Development

### Testing Discovery
```bash
cd /home/dev/IoT2mqtt/connectors/homekit/actions
python3 discover.py 10
```

### Testing Pairing
```bash
python3 pair.py "my_device" "AA:BB:CC:DD:EE:FF" "123-45-678" "192.168.1.100" 5001
```

### Building Docker Image
```bash
cd /home/dev/IoT2mqtt
docker build -t iot2mqtt-homekit connectors/homekit/
```

## Dependencies

- `aiohomekit==3.2.20` - HomeKit Accessory Protocol implementation
- `zeroconf>=0.132.0` - mDNS/Zeroconf for device discovery
- Python 3.11+
- `libavahi-compat-libdnssd-dev` - System library for mDNS

## Credits

- Uses [aiohomekit](https://github.com/Jc2k/aiohomekit) library (same as Home Assistant)
- Implements Apple's HomeKit Accessory Protocol (HAP)
- Part of the [IoT2mqtt](https://github.com/eduard256/IoT2mqtt) project

## License

MIT License - See main project repository
