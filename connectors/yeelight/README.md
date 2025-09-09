# Yeelight Connector for IoT2MQTT

Direct MQTT control for Yeelight WiFi bulbs and LED strips without Home Assistant layers.

## Features

- ✅ Direct local connection to Yeelight devices
- ✅ Real-time state updates
- ✅ Full RGB and color temperature control
- ✅ Brightness control
- ✅ Effects and scenes
- ✅ Group management
- ✅ Auto-discovery of devices
- ✅ Background light support (ceiling lights)

## Quick Start

### 1. Setup a new instance

```bash
python setup.py
```

This will guide you through:
- Selecting region (China/Singapore/US/Europe)
- Account login (optional for cloud)
- Device discovery and configuration
- Creating device groups

### 2. Control via MQTT

## 🎮 MQTT Control Commands

All commands are sent to topic: `IoT2mqtt/v1/instances/{instance_id}/devices/{device_id}/cmd`

### Basic Controls

#### Power On/Off
```json
{"power": true}   // Turn on
{"power": false}  // Turn off
{"toggle": true}  // Toggle state
```

#### Brightness (1-100%)
```json
{"brightness": 50}
```

#### Color Temperature (1700-6500K)
```json
{"color_temp": 3000}  // Warm white
{"color_temp": 6500}  // Cool white
```

#### RGB Color
```json
{"rgb": {"r": 255, "g": 0, "b": 0}}  // Red
{"rgb": [0, 255, 0]}                  // Green (array format)
```

#### HSV Color
```json
{"hsv": {"h": 180, "s": 100}}  // Hue: 0-359, Saturation: 0-100
```

#### Multiple Commands
```json
{
  "power": true,
  "brightness": 75,
  "rgb": {"r": 255, "g": 200, "b": 100}
}
```

### 🎨 Color Presets

#### Warm & Cozy
```json
// Soft Golden (recommended for evening)
{"rgb": {"r": 255, "g": 200, "b": 100}, "brightness": 60}

// Warm Amber
{"rgb": {"r": 255, "g": 180, "b": 60}, "brightness": 50}

// Sunset
{"rgb": {"r": 255, "g": 160, "b": 40}, "brightness": 45}

// Soft Gold
{"rgb": {"r": 255, "g": 215, "b": 130}, "brightness": 55}

// Candle Light
{"color_temp": 2200, "brightness": 40}
```

#### Cool & Fresh
```json
// Daylight
{"color_temp": 5500, "brightness": 80}

// Cool Blue
{"rgb": {"r": 100, "g": 180, "b": 255}, "brightness": 70}

// Mint
{"rgb": {"r": 150, "g": 255, "b": 200}, "brightness": 65}
```

#### Vibrant Colors
```json
// Deep Purple
{"rgb": {"r": 128, "g": 0, "b": 255}, "brightness": 60}

// Hot Pink
{"rgb": {"r": 255, "g": 20, "b": 147}, "brightness": 70}

// Lime Green
{"rgb": {"r": 50, "g": 255, "b": 50}, "brightness": 75}
```

### 🎭 Scenes & Effects

#### Predefined Scenes
```json
{"scene": "sunrise"}   // Gradual wake up
{"scene": "sunset"}    // Relaxing fade
{"scene": "romance"}   // Romantic mood
{"scene": "party"}     // Party lights
{"scene": "candle"}    // Candle flicker
{"scene": "movie"}     // Cinema mode
{"scene": "night"}     // Night light
{"scene": "reading"}   // Reading light
{"scene": "relax"}     // Relaxation
```

#### Dynamic Effects
```json
{"effect": "disco"}    // Color cycling
{"effect": "pulse"}    // Brightness pulse
{"effect": "strobe"}   // Strobe light
{"effect": "rainbow"}  // Rainbow transition
{"effect": "stop"}     // Stop all effects
```

### Background Light (Ceiling Models)
```json
{
  "background": {
    "power": true,
    "brightness": 50,
    "rgb": {"r": 255, "g": 100, "b": 0}
  }
}
```

## 📊 Reading Device State

Subscribe to: `IoT2mqtt/v1/instances/{instance_id}/devices/{device_id}/state`

Example state:
```json
{
  "online": true,
  "power": true,
  "brightness": 75,
  "color_temp": 3000,
  "color_mode": 2,
  "rgb": {"r": 255, "g": 200, "b": 100},
  "hex_color": "#ffc864",
  "hsv": {"h": 40, "s": 60, "v": 75},
  "model": "yeelink.light.strip6",
  "fw_ver": "2.0.6_0066",
  "last_update": "2025-01-15T10:30:00.123Z"
}
```

## 🏠 Home Assistant Integration

### Method 1: Auto Discovery (Recommended)

The connector will automatically publish discovery configs. Just ensure discovery is enabled in Home Assistant.

### Method 2: Manual Configuration

Add to `configuration.yaml`:

```yaml
mqtt:
  light:
    - name: "Yeelight Strip"
      unique_id: "yeelight_strip_bedroom"
      state_topic: "IoT2mqtt/v1/instances/home/devices/strip_bedroom/state"
      command_topic: "IoT2mqtt/v1/instances/home/devices/strip_bedroom/cmd"
      schema: json
      brightness: true
      color_mode: true
      supported_color_modes:
        - rgb
        - color_temp
      brightness_scale: 100
      payload_on: '{"power": true}'
      payload_off: '{"power": false}'
      state_value_template: "{{ value_json.power }}"
      brightness_value_template: "{{ value_json.brightness }}"
      brightness_command_template: '{"brightness": {{ value }} }'
      rgb_value_template: "{{ value_json.rgb.r }},{{ value_json.rgb.g }},{{ value_json.rgb.b }}"
      rgb_command_template: '{"rgb": {"r": {{ red }}, "g": {{ green }}, "b": {{ blue }} }}'
      color_temp_value_template: "{{ value_json.color_temp }}"
      color_temp_command_template: '{"color_temp": {{ value }}}'
      min_mireds: 153  # 6500K
      max_mireds: 588  # 1700K
```

## 🛠️ Testing with Tools

### Using MQTT Explorer
1. Connect to your broker (10.0.20.104:1883 with mqtt/mqtt credentials)
2. Navigate to `IoT2mqtt/v1/instances/{your_instance}/devices/{device_id}/cmd`
3. Publish JSON commands from examples above

### Using mosquitto_pub
```bash
# Turn on
mosquitto_pub -h 10.0.20.104 -u mqtt -P mqtt \
  -t "IoT2mqtt/v1/instances/home/devices/strip_bedroom/cmd" \
  -m '{"power": true}'

# Set golden color
mosquitto_pub -h 10.0.20.104 -u mqtt -P mqtt \
  -t "IoT2mqtt/v1/instances/home/devices/strip_bedroom/cmd" \
  -m '{"rgb": {"r": 255, "g": 200, "b": 100}, "brightness": 60}'

# Subscribe to state
mosquitto_sub -h 10.0.20.104 -u mqtt -P mqtt \
  -t "IoT2mqtt/v1/instances/home/devices/+/state" -v
```

## 📝 Configuration

Instance configs are stored in `instances/{name}.json`:

```json
{
  "instance_id": "home",
  "instance_type": "account",
  "connector_type": "yeelight",
  "connection": {
    "use_cloud": false,
    "discover_timeout": 5
  },
  "devices": [
    {
      "device_id": "strip_bedroom",
      "name": "Bedroom LED Strip",
      "ip": "192.168.1.100",
      "port": 55443,
      "model": "yeelink.light.strip6",
      "enabled": true,
      "auto_on": true
    }
  ],
  "update_interval": 10,
  "discovery_enabled": true,
  "discovery_interval": 300
}
```

## 🔍 Troubleshooting

### Device not responding to commands
- **Check the topic**: Commands go to `/cmd`, not `/state`
- **Verify format**: Use JSON format as shown in examples
- **Check logs**: `docker logs iot2mqtt_yeelight_{instance_name}`
- **Test connection**: Ping device IP address

### Colors look wrong
- Yeelight RGB values are 0-255
- Brightness is separate from RGB (1-100%)
- Some models don't support all features

### Can't discover devices
- Enable LAN Control in Yeelight app
- Ensure devices are on same network
- Check firewall rules for port 55443

### High latency
- Use local connection instead of cloud
- Reduce `update_interval` to 5 seconds
- Check network connectivity

## 🚀 Advanced Features

### Music Mode
```json
{"music_mode": true}  // Enable low-latency mode
```

### Custom Flows
Create custom light flows by sending multiple transitions.

### Nightlight Mode
For devices with nightlight support:
```json
{"nightlight": {"brightness": 10}}
```

## 📦 Supported Devices

- Yeelight LED Bulb (Color)
- Yeelight LED Strip
- Yeelight Ceiling Light
- Yeelight Bedside Lamp
- Yeelight Lightstrip Plus
- Mi LED Smart Bulb
- Most WiFi-enabled Yeelight products

## 🤝 Support

- Main IoT2MQTT documentation: [README.md](../../README.md)
- AI assistance guide: [CLAUDE.md](../../CLAUDE.md)
- GitHub Issues: [Report problems](https://github.com/eduard256/IoT2mqtt/issues)