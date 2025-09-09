# Template Connector for IoT2MQTT

This is a template connector showing how to implement a custom integration for IoT2MQTT.

## Features

- Direct MQTT connection with minimal latency
- Automatic device discovery (customize for your devices)
- Individual device control
- Group management
- Home Assistant discovery (optional)
- Docker containerization for isolation

## Quick Start

### 1. Setup a new instance

```bash
python setup.py
```

This will guide you through:
- Naming your instance
- Configuring connection settings
- Discovering and adding devices
- Creating device groups
- Advanced settings

### 2. Manage existing instances

```bash
python manage.py
```

This allows you to:
- View and edit configurations
- Add/remove devices
- View logs
- Restart containers
- Delete instances

### 3. Start the connector

The connector runs in Docker. After setup, start it with:

```bash
docker-compose up -d <instance_name>
```

## Customization Guide

### For Device Developers

To adapt this template for your specific devices/service:

1. **Edit `connector.py`**:
   - Implement `initialize_connection()` for your device API
   - Implement `get_device_state()` to read device status
   - Implement `set_device_state()` to control devices
   - Add device discovery logic if supported

2. **Edit `setup.py`**:
   - Customize connection settings prompts
   - Modify device discovery logic
   - Add device-specific capabilities

3. **Update `requirements.txt`**:
   - Add your device SDK or API library
   - Include any additional dependencies

4. **Modify `Dockerfile`** if needed:
   - Add system dependencies
   - Configure environment variables

### Example Implementations

#### For HTTP API devices:
```python
def initialize_connection(self):
    self.session = requests.Session()
    self.session.headers.update({
        'Authorization': f"Bearer {self.config['connection']['api_key']}"
    })

def get_device_state(self, device_id, device_config):
    response = self.session.get(f"{self.api_url}/devices/{device_id}")
    return response.json()
```

#### For Local Network devices:
```python
def initialize_connection(self):
    for device in self.config['devices']:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((device['ip'], device['port']))
        self.device_connections[device['device_id']] = sock
```

#### For WebSocket connections:
```python
def initialize_connection(self):
    self.ws = websocket.WebSocketApp(
        self.config['connection']['ws_url'],
        on_message=self.on_ws_message,
        on_error=self.on_ws_error
    )
    self.ws.run_forever()
```

## Configuration Format

Instance configurations are stored in `instances/<name>.json`:

```json
{
  "instance_id": "my_devices",
  "instance_type": "device",
  "connector_type": "template",
  "connection": {
    "host": "192.168.1.100",
    "port": 80
  },
  "devices": [
    {
      "device_id": "device_1",
      "friendly_name": "Living Room Light",
      "model": "Generic Light",
      "capabilities": {
        "power": {"settable": true},
        "brightness": {"settable": true, "min": 0, "max": 100}
      }
    }
  ],
  "update_interval": 10
}
```

## MQTT Topics

The connector publishes to these MQTT topics:

- `{base_topic}/v1/instances/{instance_id}/status` - Instance online/offline
- `{base_topic}/v1/instances/{instance_id}/devices/{device_id}/state` - Device state
- `{base_topic}/v1/instances/{instance_id}/devices/{device_id}/cmd` - Device commands
- `{base_topic}/v1/instances/{instance_id}/devices/{device_id}/events` - Device events
- `{base_topic}/v1/instances/{instance_id}/discovered` - Discovered devices

## Development

### Running in development mode

For hot reload during development:

```bash
MODE=development INSTANCE_NAME=test python main.py
```

This will watch `connector.py` and reload on changes.

### Testing

Test your connector with mock MQTT:

```python
from unittest.mock import Mock
from connector import Connector

mock_mqtt = Mock()
connector = Connector(instance_name="test")
connector.mqtt = mock_mqtt

# Test device state
state = connector.get_device_state("device_1", {})
assert state is not None

# Test command handling
result = connector.set_device_state("device_1", {}, {"power": True})
assert result == True
```

## Troubleshooting

### Connector won't start
- Check logs: `docker logs iot2mqtt_<instance_name>`
- Verify configuration in `instances/<name>.json`
- Ensure MQTT broker is accessible

### Devices not responding
- Check device is powered on and connected
- Verify IP address and credentials
- Check firewall rules

### High latency
- Reduce `update_interval` in configuration
- Check network connectivity
- Consider using local connection instead of cloud

## Support

For help creating your connector:
- See main IoT2MQTT documentation
- Check CLAUDE.md for AI assistance
- Open an issue on GitHub