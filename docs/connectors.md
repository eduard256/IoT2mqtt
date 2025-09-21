# Connector Structure and Packaging

Connectors live under `connectors/<name>/` and are packaged as standalone Docker images managed by the web container. This document explains the directory layout and expectations when authoring or debugging a connector.

## Directory Layout

```
connectors/
  <connector_name>/
    connector.py           # Entrypoint used by DockerService
    discovery.py           # Optional discovery runner
    manifest.json          # Metadata + UI schema (preferred)
    setup.json             # Legacy schema (fallback)
    icon.svg               # Optional icon served in the integrations catalog
    instances/             # Generated per-instance configs (not tracked in git)
    requirements.txt       # Python dependencies for the connector container
    Dockerfile             # Builds iot2mqtt/<connector>:latest
    README.md              # Connector-specific documentation (optional)
```

Key notes:

- The repository keeps empty `instances/` folders via `.gitkeep`. Real instance configs are generated on the host and ignored by `.gitignore`.
- Each connector may reference shared utilities through `/app/shared`, which is mounted read-only into every container.
- The Docker image name follows `iot2mqtt/<connector>:latest`. Discovery uses the same image, launched with the `python -m connector discover` command.

## Manifest and Setup

### `manifest.json`

Preferred format that supports:

- `name`, `version`, `author`, `documentation` — displayed in the UI.
- `branding` — icon (emoji or relative path), primary color, gradient background, category.
- `discovery` — flags discovery support and default runtime arguments (`timeout`, `network_mode`, `command`).
- `manual_config` / `instance_config` — form metadata used by the React `FlowSetupForm` component.

### `setup.json`

Legacy fallback. When only `setup.py` is present, `ConfigService` auto-generates a minimal schema composed of `instance_id` and `friendly_name` fields.

## Instances

- Saved under `connectors/<name>/instances/<instance_id>.json`.
- Managed exclusively via APIs: discovery add flow or manual instance creation.
- Contain device lists, connection parameters, and metadata (`created_at`, `updated_at`).
- Sensitive fields are extracted and stored separately through `SecretsManager`; plain configs remain safe to inspect.

## Icons

- `icon.svg` is optional but recommended. The backend exposes `/api/integrations/{name}/icon` for the frontend.
- Missing icons fall back to the default vectors bundled inside the frontend build (`dist/icons/default.svg` or `dist/assets/default-icon.svg`).

## Container Naming and Labels

- Runtime container name: `iot2mqtt_<connector>_<instance>`.
- Labels applied automatically:
  - `iot2mqtt.type=connector`
  - `iot2mqtt.connector=<connector>`
  - `iot2mqtt.instance=<instance>`

These labels allow the Containers page to categorize entries and map them back to integrations.

## Discovery Output Contract

- Discovery scripts should emit JSON lines containing either `{"device": {...}}` or `{"progress": <int>}` so the backend can persist results and surface live status updates.
- Devices saved in `discovered_devices.json` must include unique `id` values and the owning `integration` name. Additional metadata (IP, port, model, capabilities) improves the UX when converting to managed instances.

