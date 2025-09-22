# Xiaomi MiIO Connector

Modern web-driven configuration supporting both Xiaomi cloud accounts and manual
token entry. The entire onboarding logic lives in `setup.json`, so no CLI
scripts are required.

## Setup Options

1. **Cloud flow (recommended)** – sign in with a Xiaomi account, pick a device,
   and let the wizard fetch the token automatically.
2. **Manual flow** – provide the device IP and token if you already extracted
   credentials.

Each successful setup creates an instance file under
`instances/xiaomi_miio/` and launches a dedicated container for the runtime
connector.

## MQTT Topics

Commands: `IoT2mqtt/v1/instances/{instance_id}/devices/{device_id}/cmd`

States: `IoT2mqtt/v1/instances/{instance_id}/devices/{device_id}/state`

The command payload shape depends on the specific device category (vacuum,
purifier, fan, etc.). Refer to the connector source for detailed handlers.

## Directory Structure

- `setup.json` – describes the cloud and manual flows, including tool execution
- `actions/` – scripts for interacting with Xiaomi cloud APIs and validating
  tokens
- `connector.py` – runtime logic shared by all Xiaomi MiIO devices
- `manifest.json` – catalog metadata used by the web UI

As with every integration in the new architecture, all Xiaomi-specific logic is
contained within this folder.
