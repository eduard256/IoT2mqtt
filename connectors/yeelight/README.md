# Yeelight Connector for IoT2MQTT

Modern declarative integration for Yeelight Wi-Fi lighting. Configure instances
via the web interface using automatic discovery or manual entry – no CLI wizard
required.

## Setup Overview

1. Open the web interface and choose **Add Integration → Yeelight**.
2. Pick the **Auto Discovery** flow to scan the LAN or switch to **Manual** to
   enter an IP address and port.
3. Review the summary and press **Finish** – a dedicated container is built and
   started for the new instance.

Both flows emit the same configuration file under `instances/yeelight/` and are
entirely driven by `connectors/yeelight/setup.json`.

## MQTT Command Reference

Commands are published to:
`IoT2mqtt/v1/instances/{instance_id}/devices/{device_id}/cmd`

### Power & Brightness
```json
{"power": true}
{"power": false}
{"brightness": 75}
```

### Color Temperature & RGB
```json
{"color_temp": 3200}
{"rgb": {"r": 255, "g": 128, "b": 64}}
```

Multiple properties can be combined in one payload. The connector automatically
applies smooth transitions using the defaults stored in the instance config.

### Built-in Effects
```json
{"scene": "sunrise"}
{"scene": "night"}
{"effect": "disco"}
{"effect": "stop"}
```

## State Topic

Subscribe to `IoT2mqtt/v1/instances/{instance_id}/devices/{device_id}/state` to
receive updates such as power, brightness, RGB, and firmware information.

## File Layout

- `setup.json` – declarative setup flows for the web UI
- `actions/` – isolated helper scripts executed by the test-runner container
- `connector.py` – runtime implementation used inside the connector container
- `requirements.txt` – Python dependencies for runtime and actions
- `manifest.json` – metadata consumed by the integration catalog

This layout keeps all Yeelight-specific logic inside `connectors/yeelight`,
which means new integrations can be added without touching the global frontend
or backend.
