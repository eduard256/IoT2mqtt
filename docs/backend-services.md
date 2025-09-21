# Backend Services Overview

This document explains the core backend services that power the web API and connector orchestration.

## ConfigService

`services/config_service.py`

Responsibilities:

- Determine the runtime base path. The service first checks `IOT2MQTT_PATH`, then walks up from its own location until it finds a directory containing `docker-compose.yml`, finally falling back to the current working directory.
- Provide resolved paths for: `.env`, `connectors/`, `secrets/`, `discovered_devices.json`, `discovery_config.json`, and the compiled frontend (`frontend/dist` or `web/frontend/dist`).
- Guarantee required directories exist by calling `mkdir(parents=True, exist_ok=True)` for `connectors/` and `secrets/` during initialization.
- Load and persist `.env` values with file locking to avoid concurrent write issues.
- Enumerate connectors and instances, generating backup copies when configs are updated.
- Act as the single source of truth for connector branding (icon fallback, display name) and setup schemas.

Key details:

- File locking uses `fcntl` for exclusive access, which is safe on Linux (the supported target).
- When the frontend build is missing, `_detect_frontend_dist_path()` still returns the expected location so static routes stay predictable.

## DockerService

`services/docker_service.py`

Responsibilities:

- Manage connector containers using the host Docker socket (`unix:///var/run/docker.sock`).
- Detect the host project path by inspecting the mounts of the running web container. If `/app/connectors` is mounted, the host path is set to the parent directory of that mount. Falling back to `HOST_IOT2MQTT_PATH` or the resolved base path ensures compatibility when the service runs outside Docker.
- Build images on demand (`build_image`), create or restart connector containers (`create_container`, `create_or_update_container`), and produce lightweight container summaries (`list_containers`, `get_container_info`).
- Mount host directories into connector containers:
  - `shared/` (read-only shared libs)
  - `connectors/<name>/instances` (instance configurations)
  - `.env` (for MQTT settings and other env vars)

Container naming and labels:

- Containers are named `iot2mqtt_<connector>_<instance>` and labeled with `iot2mqtt.type=connector` so the UI can filter them.
- Docker images follow the tag `iot2mqtt/<connector>:latest`.

## MQTTService

`services/mqtt_service.py`

Responsibilities:

- Wrap the `paho-mqtt` client to provide connection management, publish helpers, and topic subscriptions.
- Expose connection state to the FastAPI app so `/api/health` and other endpoints can report broker availability.
- Handle reconnect logic and default options using `.env` values (host, port, credentials, QoS, retain, keepalive).

MQTT is initialized during the FastAPI lifespan; when the app shuts down, the service disconnects cleanly.

## Discovery Flow

Key actors: `ConfigService`, `DockerService`, `api/discovery.py`.

1. When discovery starts, the API ensures the connector supports discovery via its manifest/setup.
2. A short-lived container is launched with the connector image in discovery mode (`python -m connector discover`).
3. Logs are streamed to keep track of progress; JSON entries with `device` or `progress` keys are parsed and stored in `discovery_sessions`.
4. Discovered devices are persisted into `discovered_devices.json` (under the runtime base path). Adding a device writes a new instance file under `connectors/<name>/instances/` then creates or restarts the connector container via `DockerService`.
5. WebSockets (`/api/discovery/{session_id}`) push live updates to the frontend.

## Static Assets Serving

`main.py` consults `ConfigService.frontend_dist_path` to mount the SPA build. The app exposes:

- `/assets`, `/icons`, `/locales` for static bundles if those directories exist.
- Direct routes for PWA files such as `/sw.js` and `/manifest.json`.
- A catch-all handler that serves `index.html` for any non-API path so client-side routing works.

This setup allows identical behavior whether the backend runs inside the official Docker image or directly from a local checkout.

