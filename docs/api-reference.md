# API Reference (Core Endpoints)

This document lists the main REST endpoints exposed by the FastAPI backend. All routes require a valid JWT unless noted otherwise. Tokens are obtained via `/api/auth/login`.

## Authentication

### POST `/api/auth/login`

- Body: `{ "key": "<access_key>" }`
- On first login, the provided key is hashed and stored in `.env` via `ConfigService`.
- Response: `{ "success": true, "message": "Login successful", "token": "<jwt>" }`

### GET `/api/auth/check`

- Validates the JWT supplied in the `Authorization: Bearer` header.
- Response: `{ "authenticated": true, "user": "user" }`

## Health

### GET `/api/health`

- No auth required.
- Returns FastAPI uptime info plus Docker and MQTT availability flags.
- Example: `{ "status": "healthy", "mqtt_connected": true, "docker_available": true }`

## Integrations Catalog

### GET `/api/integrations`

- Returns every configured integration instance, grouped by connector.
- Response (list): each item contains `name`, `display_name`, `instances_count`, `status`, `instances` (array of instance summaries).
- `status` values: `connected`, `error`, `offline`, `configuring`.

### GET `/api/integrations/{integration_name}/instances`

- Lists all instances for a specific connector.
- Response: array of `IntegrationInstance` objects with `instance_id`, `friendly_name`, `status`, `device_count`, etc.

### GET `/api/integrations/{name}/meta`

- Combines setup schema (`setup.json` or auto-generated), branding, and icon availability.

### GET `/api/integrations/{name}/icon`

- Serves the connector SVG if present. Otherwise falls back to the default icons inside the compiled frontend (`dist/icons/default.svg` or `dist/assets/default-icon.svg`).

### POST `/api/integrations/{name}/discover`

- Triggers discovery for a connector. Body accepts optional `timeout` and `network_mode`, defaulting to 30 seconds and `host`.
- Response: `{ "session_id", "status": "started", "websocket_url": "/api/discovery/<session>" }`.

## Discovery Management

### GET `/api/discovery/devices`

- Returns the current content of `discovered_devices.json`.
- Response: array of devices with fields like `id`, `integration`, `ip`, `model`, `capabilities`, `added`.

### POST `/api/discovery/devices/{device_id}/add`

- Body: `{ "device_id", "instance_id", "friendly_name", "config": { ... } }`.
- Action: writes a new instance file under `connectors/<integration>/instances/` and starts/updates the connector container.

### DELETE `/api/discovery/devices/{device_id}`

- Removes a discovered device entry (does not delete existing instances).

### WebSocket `/api/discovery/{session_id}`

- Streams JSON payloads with fields: `status`, `devices`, `progress`, `logs`, optionally `error` on failure.

## Instance Lifecycle

Core routes (see `api/instances.py` for full list):

- `GET /api/instances` — list all instances across connectors.
- `GET /api/instances/{connector}/{instance_id}` — load a single instance configuration (secrets are reinjected).
- `POST /api/instances/{connector}` — create a new instance; accepts sanitized config, delegates to `ConfigService` + `DockerService`.
- `DELETE /api/instances/{connector}/{instance_id}` — remove config and stop container.

## Device Inventory

### GET `/api/devices`

- Aggregates all devices defined in connector instance configs.
- Response shape: `{ "success": true, "message": "Found <n> devices", "devices": [ ... ] }`.
- Each device entry contains: `connector_type`, `instance_id`, `device_id`, `friendly_name`, `device_type`, `device_class`, `state`, `capabilities`, `online`, `enabled`, `room`, `model`, `manufacturer`, `last_update`.

### POST `/api/devices/{instance_id}/{device_id}/command`

- Body: `{ "command": { ... } }`.
- Publishes the command to the connector-specific MQTT topic. Response mirrors `{ "success": true, "message": "Command dispatched" }` on success.

## Docker Operations

Routes under `/api/docker` reflect container management and require JWT auth:

- `GET /api/docker/containers` — returns an array of container summaries including `id`, `name`, `image`, `status`, `state`, `labels`, and connector metadata if available.
- `POST /api/docker/containers/{container_id}/start|stop|restart` — lifecycle actions. Response: `{ "success": true, "message": "Container started" }` (or respective message).
- `DELETE /api/docker/containers/{container_id}?force=true|false` — remove connector container.
- `GET /api/docker/containers/{container_id}/logs?lines=100` — returns structured log lines for UI display.

### WebSocket `/ws/logs/{container_id}`

- Streams JSON log objects for the specified container. Used by the Containers page for live updates.

## MQTT Utilities

Key routes under `/api/mqtt`:

- `GET /api/mqtt/status` — broker connection state.
- `GET /api/mqtt/config` / `POST /api/mqtt/config` — read and update `.env` MQTT settings.
- `POST /api/mqtt/publish` — publish raw MQTT payloads (`{ "topic": "...", "payload": "...", "qos": 0 }`).

### WebSocket `/ws/mqtt`

- Streams MQTT messages (topics and payloads). The frontend subscribes after login, sending the JWT as a query parameter.

