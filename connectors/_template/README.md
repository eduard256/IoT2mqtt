# Simple Connector Template

This template demonstrates the simplest connector pattern: a single Python process using the BaseConnector helper class for polling-based device communication.

## 🎯 Choosing the Right Template

IoT2MQTT v2.0 supports connectors of varying complexity, from simple Python scripts to multi-language multi-process implementations. **This template represents the simplest pattern** and is ideal for straightforward polling-based device integrations.

### ✅ Use This Template When:

- Your connector communicates with devices using a **single protocol** (HTTP, Modbus, serial, etc.)
- **Polling-based state updates** are sufficient (query device every N seconds)
- Device communication can be handled by **synchronous Python code**
- You don't need to integrate existing applications written in other languages
- Device communication latency allows for **sequential processing**
- You're building a **simple integration** without complex coordination needs

### 🔀 Consider Multi-Process Template When:

If your connector needs any of the following, use `_template-multiprocess` instead:

- **Multiple languages** (Python + Node.js + Go + etc.)
- **Parallel processing** of device communications
- **Wrapping existing applications** (Zigbee2MQTT, go2rtc, etc.)
- **Separate processes** for different concerns (streaming + command processing)
- **Event-driven architecture** rather than polling
- **Real-time streaming** (video, audio, sensor data)

👉 **See:** [`_template-multiprocess/`](../_template-multiprocess/) for complex multi-service connectors with supervisord process management.

## 📚 Complete Documentation

This README provides quick-start guidance for the simple template. For comprehensive connector development documentation, see:

**📖 [`docs/CONNECTOR_SPEC.md`](../../docs/CONNECTOR_SPEC.md)** - Complete connector specification including:
- Mandatory MQTT contract (topic patterns, payload formats)
- Environment variable requirements
- Architectural patterns for all complexity levels
- Troubleshooting and debugging strategies
- Best practices and examples

## 🏗️ Architecture Overview

This template implements a **single-process polling architecture**:

```
┌─────────────────────────────────────┐
│  Docker Container (one instance)    │
│                                     │
│  ┌───────────────────────────────┐ │
│  │  Python Process (main.py)     │ │
│  │                               │ │
│  │  ┌─────────────────────────┐ │ │
│  │  │  BaseConnector          │ │ │
│  │  │  - MQTT Client          │ │ │
│  │  │  - Polling Loop         │ │ │
│  │  │  - Config Management    │ │ │
│  │  └─────────────────────────┘ │ │
│  │           ▲                   │ │
│  │           │                   │ │
│  │  ┌────────┴────────────────┐ │ │
│  │  │  Your Connector Class   │ │ │
│  │  │  - initialize_connection│ │ │
│  │  │  - get_device_state     │ │ │
│  │  │  - set_device_state     │ │ │
│  │  └─────────────────────────┘ │ │
│  └───────────────────────────────┘ │
│                                     │
│  Polls devices → publishes to MQTT │
└─────────────────────────────────────┘
```

## 📁 File Structure

```
connectors/_template/
├── Dockerfile              # Container build definition (mandatory)
├── main.py                # Entry point (mandatory)
├── connector.py           # Your connector implementation (mandatory)
├── requirements.txt       # Python dependencies (mandatory)
├── setup.json            # Web UI configuration flow (mandatory)
├── README.md             # This file (recommended)
└── actions/              # Setup-time validation scripts (optional)
    └── example.py        # Executed by test-runner during setup
```

**Note:** The `actions/` scripts run in the **test-runner container** during setup, while the connector code runs in the **connector's runtime container**.

## 🔧 BaseConnector: Optional Helper Class

`BaseConnector` is a **convenience class, not a requirement**. It provides useful abstractions for polling-based connectors:

### What BaseConnector Provides:

- **Configuration loading** from instance JSON files
- **MQTT client initialization** with connection management
- **Automatic polling loop** that calls your methods at regular intervals
- **Command handling** for device control via MQTT
- **Error handling** and logging infrastructure

### When to Use BaseConnector:

✅ For **polling-based** connectors (most common case)
✅ When Python is your **only language**
✅ When you want **quick development** with less boilerplate

### When NOT to Use BaseConnector:

❌ **Event-driven** connectors (WebSocket, SSE, callbacks)
❌ **Multi-language** connectors (use multi-process template)
❌ Need **precise control** over MQTT communication
❌ Non-Python connectors

**Alternative:** Implement the MQTT contract directly in any language. See CONNECTOR_SPEC.md for the contract specification.

## 🚀 Quick Start

### 1. Copy Template

```bash
cp -r connectors/_template connectors/my-connector
cd connectors/my-connector
```

### 2. Implement Connector Class

Edit `connector.py` and implement the abstract methods:

```python
from base_connector import BaseConnector

class Connector(BaseConnector):

    def initialize_connection(self):
        """
        Called once at startup
        Establish connections to devices/services
        """
        # Initialize your device communication
        # Example: self.device = MyDevice(self.config['host'])
        pass

    def cleanup_connection(self):
        """
        Called at shutdown
        Clean up resources
        """
        # Close connections, release resources
        pass

    def get_device_state(self, device_id: str, device_config: dict):
        """
        Called periodically by BaseConnector's polling loop
        Query device and return current state

        Returns: dict with device state or None if unavailable
        """
        # Query device
        # Return state dictionary
        return {
            "online": True,
            "temperature": 22.5,
            "humidity": 45
        }

    def set_device_state(self, device_id: str, device_config: dict, state: dict):
        """
        Called when MQTT commands are received
        Apply state changes to device

        Returns: bool (True if successful)
        """
        # Send commands to device
        # Return success/failure
        return True
```

### 3. Configure Dependencies

Edit `requirements.txt` with your Python dependencies:

```
# Add your device communication libraries
# Example:
# requests>=2.28.0
# pyserial>=3.5
# pymodbus>=3.0.0
```

### 4. Customize Setup Flow

Edit `setup.json` to define your configuration flow for the Web UI. See existing examples for field types and validation.

### 5. Add Validation Actions (Optional)

Create scripts in `actions/` to validate configuration during setup. These run in the test-runner container and can test connectivity, discover devices, etc.

### 6. Build and Test

```bash
# Build Docker image
docker build -t iot2mqtt_my-connector:latest .

# Test locally (requires MQTT broker)
docker run --rm -it \
  -e INSTANCE_NAME=test_instance \
  -e CONNECTOR_TYPE=my-connector \
  -e MQTT_HOST=localhost \
  -e MQTT_PORT=1883 \
  -v ./../../shared:/app/shared:ro \
  iot2mqtt_my-connector:latest
```

## 🌍 Environment Variables

Your connector receives these environment variables automatically:

### Injected by docker_service:

- **`INSTANCE_NAME`** - Unique instance identifier (e.g., `yeelight_livingroom`)
  - Used for config loading and MQTT topic construction
- **`CONNECTOR_TYPE`** - Connector type identifier (e.g., `yeelight`)
  - Available for logging and validation
- **`MODE`** - Operating mode (`production` or `development`)

### From mounted .env file:

- **`MQTT_HOST`** - MQTT broker address
- **`MQTT_PORT`** - MQTT broker port
- **`MQTT_USERNAME`** - MQTT authentication username
- **`MQTT_PASSWORD`** - MQTT authentication password
- **`MQTT_BASE_TOPIC`** - Base topic prefix (default: `IoT2mqtt`)
- **`LOG_LEVEL`** - Logging verbosity (DEBUG, INFO, WARNING, ERROR)

Access these in your code via `os.getenv()` or through BaseConnector's configuration system.

## 📊 Decision Framework

**Use this flowchart to choose the right template:**

```
START: Building a new connector
    ↓
    Can it be implemented in a single Python process?
    ├─ YES → Continue ↓
    └─ NO → Use _template-multiprocess

    Does it need polling-based state updates?
    ├─ YES → Use this template (_template)
    └─ NO (event-driven/streaming) → Consider direct MQTT implementation

    Are you wrapping an existing application?
    ├─ NO → Use this template (_template)
    └─ YES → Use _template-multiprocess with wrapper pattern

    ↓
✅ Use _template (this directory)
```

**Still unsure?** Start with this simple template. You can always refactor to multi-process later if needed.

## 📝 MQTT Contract

All connectors must implement the IoT2MQTT MQTT contract. BaseConnector handles this automatically, but you should understand the contract:

### Topics Your Connector Uses:

**Subscribe (receive commands):**
```
{BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/cmd
{BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/get
{BASE_TOPIC}/v1/instances/{instance_id}/meta/request/+
```

**Publish (send state):**
```
{BASE_TOPIC}/v1/instances/{instance_id}/status (online/offline with LWT)
{BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/state
{BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/error
```

BaseConnector handles subscription and publishing for you. Your job is to implement the state query and command execution methods.

**For complete contract details:** See [`docs/CONNECTOR_SPEC.md`](../../docs/CONNECTOR_SPEC.md)

## 🛠️ Customization Guide

### Adding Device Configuration

In `setup.json`, add form fields for your device parameters:

```json
{
  "type": "text",
  "name": "device_ip",
  "label": "Device IP Address",
  "required": true
}
```

These values appear in your connector's config and can be accessed via `self.config['device_ip']`.

### Adding Discovery

Implement `discover_devices()` method in your connector class (optional):

```python
def discover_devices(self) -> List[Dict[str, Any]]:
    """Discover devices on the network"""
    # Return list of discovered devices
    return [{"device_id": "...", "ip": "...", ...}]
```

### Handling Multiple Devices

BaseConnector automatically iterates over `self.config['devices']` in the polling loop. Each device calls `get_device_state()` and `set_device_state()` independently.

### Custom Update Intervals

Set `update_interval` in your instance config (seconds between polls):

```json
{
  "update_interval": 30
}
```

## 🐛 Troubleshooting

### Connector Not Starting

**Check logs:**
```bash
docker logs <container_name>
```

**Common issues:**
- Missing environment variables (INSTANCE_NAME, MQTT_*)
- Config file not found (check volume mounts)
- Python import errors (missing dependencies in requirements.txt)

### MQTT Connection Failed

**Verify MQTT settings:**
```bash
docker exec <container> env | grep MQTT
```

**Common issues:**
- Wrong MQTT broker address
- Authentication credentials incorrect
- Network connectivity issues

### Devices Not Responding

**Check device connectivity from container:**
```bash
docker exec <container> ping <device_ip>
docker exec <container> curl http://<device_ip>
```

**Common issues:**
- Network mode incorrect (try `network_mode: "host"` in docker-compose)
- Firewall blocking connections
- Device not on same network as container

### For More Troubleshooting

See comprehensive debugging guide in [`docs/CONNECTOR_SPEC.md`](../../docs/CONNECTOR_SPEC.md)

## 🎓 Best Practices

1. **Keep it simple** - Don't add unnecessary complexity
2. **Handle errors gracefully** - Return None from get_device_state() on errors
3. **Log meaningful messages** - Use logger for debugging
4. **Test locally first** - Before deploying to IoT2MQTT
5. **Use config for everything** - Avoid hardcoding parameters
6. **Implement health checks** - Return proper state even when devices offline
7. **Document your connector** - Update README with specific instructions

## 📚 Related Templates and Documentation

- **Multi-Process Template:** [`_template-multiprocess/`](../_template-multiprocess/) - For complex multi-language connectors
- **Complete Specification:** [`docs/CONNECTOR_SPEC.md`](../../docs/CONNECTOR_SPEC.md) - Full connector architecture guide
- **Example Connector:** [`yeelight/`](../yeelight/) - Real-world implementation using this template

## 💡 Examples

### Simple HTTP Device

```python
def get_device_state(self, device_id: str, device_config: dict):
    response = requests.get(f"http://{device_config['ip']}/status")
    return response.json()
```

### Modbus Device

```python
from pymodbus.client import ModbusTcpClient

def initialize_connection(self):
    self.client = ModbusTcpClient(self.config['modbus_host'])

def get_device_state(self, device_id: str, device_config: dict):
    result = self.client.read_holding_registers(0, 10)
    return {"registers": result.registers}
```

### Serial Device

```python
import serial

def initialize_connection(self):
    self.port = serial.Serial(self.config['serial_port'], 9600)

def get_device_state(self, device_id: str, device_config: dict):
    self.port.write(b'STATUS\r\n')
    response = self.port.readline()
    return {"status": response.decode()}
```

## 🚀 Next Steps

1. ✅ Copy this template to your connector directory
2. ✅ Implement the three abstract methods
3. ✅ Add dependencies to requirements.txt
4. ✅ Customize setup.json for your configuration
5. ✅ Build and test locally
6. ✅ Read CONNECTOR_SPEC.md for advanced patterns
7. ✅ Deploy through IoT2MQTT Web UI

---

**Need more complexity?** Check out [`_template-multiprocess/`](../_template-multiprocess/) for multi-language, multi-process connectors.

**Need help?** See comprehensive documentation at [`docs/CONNECTOR_SPEC.md`](../../docs/CONNECTOR_SPEC.md)
