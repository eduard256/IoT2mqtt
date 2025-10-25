# HomeKit Connector for IoT2MQTT

Full-featured HomeKit integration with complete feature parity to Home Assistant's HomeKit Controller component.

## Features

- ✅ **All HomeKit Transports:**
  - IP/TCP (HAP over WiFi/Ethernet)
  - CoAP (Thread network devices)
  - BLE (Bluetooth Low Energy) - *coming soon*

- ✅ **Complete Platform Support:**
  - Lights (on/off, brightness, color temperature, RGB, HSV)
  - Switches & Outlets
  - Sensors (temperature, humidity, light, air quality, battery, energy)
  - Binary Sensors (motion, contact, leak, smoke, occupancy, CO)
  - Climate (thermostats, heaters, coolers)
  - Locks
  - Covers (blinds, garage doors, windows)
  - Fans (speed, swing, direction)

- ✅ **Advanced Features:**
  - Push notifications via event subscriptions
  - Polling fallback for non-event devices
  - Multi-service accessories support
  - Vendor-specific characteristics (Eve, Ecobee, Aqara)
  - Thread provisioning (BLE → CoAP migration)
  - HomeKit bridge support (up to 100+ accessories)
  - Home Assistant MQTT Discovery

## Architecture

**Multi-Process Design:**
- **Process 1:** MQTT Bridge (BaseConnector) - handles MQTT communication
- **Process 2:** HAP Service (AsyncIO/FastAPI) - handles HomeKit protocol via aiohomekit
- **IPC:** HTTP API on localhost:8765
- **Supervisor:** Manages both processes with auto-restart

## Setup

### Discovery Flow

1. Open IoT2mqtt web interface
2. Navigate to Integrations → Add Integration → HomeKit
3. Choose "Auto Discovery"
4. Select discovered device from list
5. Enter 8-digit PIN code (format: XXX-XX-XXX)
6. Wait for pairing to complete
7. Review discovered accessories
8. Finish setup

### Manual Entry Flow

1. Open IoT2mqtt web interface
2. Navigate to Integrations → Add Integration → HomeKit
3. Choose "Manual Entry"
4. Enter device IP address and PIN code
5. Complete pairing
6. Finish setup

## Configuration

### Instance Configuration

One instance can manage up to 100 HomeKit devices. Each device requires pairing.

**Example configuration:**
```json
{
  "instance_id": "homekit_main",
  "connector_type": "homekit",
  "config": {
    "hap_service_port": 8765
  },
  "devices": [
    {
      "device_id": "living_room_light",
      "pairing_id": "XX:XX:XX:XX:XX:XX",
      "aid": 1,
      "name": "Living Room Light",
      "model": "Philips Hue",
      "category": "LIGHTBULB",
      "connection": "IP",
      "ip": "192.168.1.100",
      "port": 55443,
      "enabled": true
    }
  ]
}
```

### Pairing Data (Secrets)

Pairing credentials are stored in Docker secrets at:
```
/run/secrets/{instance_name}_homekit_pairing
```

Format:
```
pairing_id=XX:XX:XX:XX:XX:XX
AccessoryLTPK=base64_encoded_public_key
iOSDeviceLTPK=base64_encoded_public_key
iOSDeviceLTSK=base64_encoded_secret_key
```

## MQTT Topics

### State Topics

```
IoT2mqtt/v1/instances/{instance_id}/devices/{device_id}/state
```

Example state:
```json
{
  "timestamp": "2025-10-25T15:30:00Z",
  "device_id": "living_room_light",
  "state": {
    "power": true,
    "brightness": 75,
    "color_temp": 3200,
    "hue": 180,
    "saturation": 50,
    "online": true
  }
}
```

### Command Topics

```
IoT2mqtt/v1/instances/{instance_id}/devices/{device_id}/cmd
```

Example command:
```json
{
  "power": true,
  "brightness": 80,
  "color_temp": 4000
}
```

### Event Topics (for doorbells, buttons)

```
IoT2mqtt/v1/instances/{instance_id}/devices/{device_id}/events
```

## Supported Devices

### Tested Devices

- Philips Hue (lights)
- Eve Energy (smart plugs with energy monitoring)
- Aqara sensors (motion, door/window, temperature/humidity)
- Ecobee thermostats
- August/Yale locks
- Lutron Caseta (via HomeKit bridge)

### HomeKit Bridge Devices

Devices connected through HomeKit bridges (like Philips Hue Bridge, Lutron Bridge) are fully supported. Each bridged accessory appears as a separate device in IoT2mqtt.

## Troubleshooting

### Device Not Found

- Ensure device is on same network
- Check device is in pairing mode
- Verify mDNS/Bonjour is working on network
- Try manual entry with IP address

### Authentication Failed

- Verify PIN code is correct
- Check device isn't already paired to another controller
- Unpair from Apple Home if previously configured
- Reset device to factory settings if needed

### Connection Drops

- Check network stability
- Verify device firmware is up to date
- Review container logs for errors
- Restart connector instance

### No Push Updates

- Verify characteristics support events ('ev' permission)
- Check SSE connection in HAP service logs
- Fallback polling should still work

## Development

### Project Structure

```
connectors/homekit/
├── Dockerfile               # Container image
├── main.py                 # Supervisord launcher
├── supervisord.conf        # Process configuration
├── connector.py            # MQTT Bridge (BaseConnector)
├── hap_service.py          # HAP Protocol Service (AsyncIO)
├── entity_mapper.py        # Characteristic → State mapping
├── characteristics.py      # Platform-specific handlers
├── workarounds.py          # Device-specific fixes
├── requirements.txt        # Python dependencies
└── actions/
    ├── discover.py         # mDNS discovery
    ├── pair.py             # Pairing flow
    ├── validate.py         # Connection validation
    └── unpair.py           # Unpair device
```

### Dependencies

- `aiohomekit==3.2.20` - HomeKit protocol implementation
- `zeroconf==0.132.2` - mDNS/DNS-SD discovery
- `fastapi==0.109.0` - AsyncIO web framework
- `paho-mqtt==2.1.0` - MQTT client
- `supervisor==4.2.5` - Process management

## Limitations

- **BLE Transport:** Not yet implemented (requires privileged containers)
- **Cameras:** Basic snapshot support only, full RTP streaming coming soon
- **Thread Provisioning:** Requires Thread Border Router in network

## License

MIT License - Same as IoT2MQTT project

## Credits

Based on Home Assistant's HomeKit Controller integration with full feature parity.

- [aiohomekit](https://github.com/Jc2k/aiohomekit) - Python HomeKit implementation
- [Home Assistant](https://www.home-assistant.io/) - Reference implementation
