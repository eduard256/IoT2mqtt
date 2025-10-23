# Declarative Setup Flows

IoT2MQTT renders integration wizards entirely from JSON. This document explains
how to author `setup.json`, how the backend validates schemas, and how the
frontend interprets each section.

## Schema Overview

Every connector ships a single `setup.json` with the following structure:

```json
{
  "version": "1.0.0",
  "display_name": "Yeelight",
  "description": "Control Yeelight smart lighting",
  "author": "IoT2MQTT",
  "requirements": { "network": "host" },
  "branding": { "icon": "💡", "category": "lighting" },
  "tools": { "discover": { "entry": "actions/discover.py" } },
  "flows": [
    { "id": "auto", "name": "Auto Discovery", "default": true, "steps": [...] }
  ]
}
```

### Metadata

- `version`, `display_name`, `description`, `author` – surfaced in the
  integrations catalog.
- `requirements` – referenced when Docker containers are created
  (e.g. `network: "host"`).
- `branding` – overrides icon, color, and category badges in the UI.
- `tools` – registry of scripts executed by the test runner. Each entry
  specifies `entry`, optional `timeout`, network access (`none`, `local`,
  `internet`), extra environment variables, and required secret names.

### Flows

`flows` is an ordered list of scenarios. Each flow must contain at least one
step; the first flow marked with `"default": true` becomes the initial view in
`FlowSetupForm`.

Available step types:

| Type        | Description                                                                     |
|-------------|---------------------------------------------------------------------------------|
| `form`      | Renders a form defined by `schema.fields`. Supports text, password, select, etc. See [Advanced Fields](#advanced-fields) for UI optimization.|
| `tool`      | Executes a registered tool. Input templates are resolved before invocation.     |
| `select`    | Displays selectable cards populated from resolved data. Supports multi-select.  |
| `summary`   | Shows read-only values before final confirmation.                               |
| `message`   | Simple informational card.                                                      |
| `oauth`     | Launches the OAuth flow for a configured provider.                              |
| `instance`  | Final step that posts the payload to `/api/instances`.                          |
| `discovery` | Presentational step; currently rendered as a message placeholder.              |

### Actions

Each step may expose `actions`: clickable buttons rendered alongside the
navigation controls. Supported actions:

- `goto_flow` – switch to another flow by `id`.
- `open_url` – open external documentation in a new tab.
- `reset_flow` – clear local state and restart the flow.
- `rerun_step` – re-executes the current tool (useful for manual retries).

Actions are optional and can include `confirm` metadata to display a client-side
confirmation dialog.

## State and Templating

The frontend exposes a single context during template resolution:

- `form.<step_id>` – values submitted from form steps.
- `tools.<key>` – responses from tool executions. The key defaults to the tool
  name but can be overridden via `output_key`.
- `selection.<key>` – values chosen in select steps.
- `oauth.<provider>` – session info resolved from the OAuth callback.
- `integration` – metadata about the connector being configured.

Templates use `{{ path.to.value }}` placeholders. If the template consists of a
single placeholder (e.g. `"{{ form.details.instance_id }}"`) the raw value is
returned; otherwise the placeholder is interpolated into the string. Nested
objects and arrays are resolved recursively via `resolveDeep`.

## OAuth Integration

OAuth providers are configured through `config/oauth/<provider>.json` and served
by `OAuthService`. To add a step:

```json
{
  "id": "authorize",
  "type": "oauth",
  "title": "Sign in",
  "oauth": {
    "provider": "example",
    "scopes": ["device.read"],
    "redirect_uri": "https://your-host/api/oauth/example/callback"
  },
  "auto_advance": true
}
```

The frontend opens a popup pointing to `/api/oauth/{provider}/session`. When the
callback succeeds, the flow stores the returned session inside
`flowState.oauth[provider]`, making it available for subsequent steps and the
final instance payload.

## Secrets Handling

`ConfigService.save_instance_with_secrets` separates sensitive values before
writing the instance file. Fields whose keys contain `password`, `token`,
`secret`, etc., plus any entries explicitly provided via `secrets` within the
`instance` step, are encrypted and stored in `secrets/instances/<instance>.secret`.
The clean JSON under `instances/<connector>/<instance>.json` references them via
placeholders and is safe to inspect or version locally.

Inside containers, Docker secrets are mounted under `/run/secrets/<instance>_creds`
and injected back into the runtime configuration by `BaseConnector`.

## Actions Directory

Tool scripts must:

1. Accept input through `stdin` in the `{ "input": {...} }` envelope.
2. Write a JSON object to `stdout` shaped as
   `{ "ok": true/false, "result" | "error" }`.
3. Return exit code `0` for both success and handled failures (the web UI reads
   the JSON payload).

The test runner runs every tool inside its own container, so scripts can install
extra dependencies by extending the integration’s `requirements.txt`.

## Advanced Fields

Form fields can be marked as `"advanced": true` to reduce UI clutter for common
use cases. Advanced fields are hidden behind a "Show Advanced" toggle button that
appears only when at least one field has this flag.

```json
{
  "type": "form",
  "schema": {
    "fields": [
      {
        "type": "text",
        "name": "friendly_name",
        "label": "Friendly name",
        "required": true
      },
      {
        "type": "text",
        "name": "instance_id",
        "label": "Instance ID",
        "placeholder": "auto",
        "description": "Leave empty to auto-generate from friendly name",
        "advanced": true
      },
      {
        "type": "number",
        "name": "port",
        "label": "Port",
        "default": 55443,
        "advanced": true
      }
    ]
  }
}
```

### Instance ID Auto-Generation

Instance IDs are **automatically generated by the backend** for all connectors when
`instance_id` is not provided, empty, or set to `"auto"`.

**Generation Format:**
```
{connector_name}_{random6}
```

Where `random6` is 6 random lowercase alphanumeric characters (a-z, 0-9).

**Examples:**
- `yeelight_a1b2c3`
- `cameras_x9y8z7`
- `yeelight_k3j5n2`

**How It Works:**

1. Frontend sends `instance_id: null` or omits the field entirely
2. Backend generates unique ID using `ConfigService.generate_unique_instance_id()`
3. Backend validates uniqueness and retries if collision occurs (max 10 attempts)
4. If all attempts fail, uses timestamp-based fallback: `{connector}_{HHMMSS}`

**Benefits:**

- ✅ **Multiple instances supported** - Create `yeelight_abc123`, `yeelight_xyz789`, etc.
- ✅ **No collisions** - Backend guarantees uniqueness
- ✅ **No configuration needed** - Works automatically for all connectors
- ✅ **Clean separation** - One instance per device group or location

**For Connector Developers:**

Simply omit `instance_id` from your `setup.json` instance step. The system handles
generation automatically. No connector-specific code required.

## Parasitic Connector Setup Pattern

Parasitic connectors extend existing device functionality by publishing additional state fields to parent device MQTT topics while maintaining independent lifecycle and control. The `mqtt_device_picker` field type automatically provides all information needed to configure parasitic attachment.

### Concept

Instead of creating new devices, parasitic connectors:
1. Select existing parent devices via `mqtt_device_picker`
2. Inherit parent device IDs
3. Publish extension fields to parent MQTT topics
4. Maintain independent control through own CMD topics

### Basic Setup Flow Example

Motion detection parasitic connector for cameras:

```json
{
  "flows": [{
    "id": "main",
    "name": "Add Motion Detection",
    "steps": [
      {
        "id": "select_camera",
        "type": "form",
        "title": "Select Camera",
        "description": "Choose camera to add motion detection",
        "schema": {
          "fields": [{
            "type": "mqtt_device_picker",
            "name": "camera_device",
            "label": "Camera to Monitor",
            "required": true,
            "config": {
              "connector_type": "cameras",
              "extract_fields": ["ip", "stream_urls.rtsp", "name"],
              "save_mode": "extracted_fields"
            }
          }]
        }
      },
      {
        "id": "motion_settings",
        "type": "form",
        "title": "Motion Detection Settings",
        "schema": {
          "fields": [
            {
              "type": "number",
              "name": "sensitivity",
              "label": "Sensitivity (0.1 - 1.0)",
              "default": 0.7,
              "min": 0.1,
              "max": 1.0,
              "step": 0.1
            },
            {
              "type": "select",
              "name": "method",
              "label": "Detection Method",
              "options": [
                {"value": "ffmpeg", "label": "FFmpeg (fast)"},
                {"value": "opencv", "label": "OpenCV (accurate)"}
              ],
              "default": "ffmpeg"
            }
          ]
        }
      },
      {
        "id": "create_instance",
        "type": "instance",
        "instance": {
          "connector_type": "cameras-motion",
          "friendly_name": "Motion Detection",
          "config": {
            "parasite_targets": [{
              "mqtt_path": "{{ form.select_camera.camera_device.mqtt_path }}",
              "device_id": "{{ form.select_camera.camera_device.device_id }}",
              "instance_id": "{{ form.select_camera.camera_device.instance_id }}",
              "extracted_data": "{{ form.select_camera.camera_device.extracted_data }}"
            }],
            "sensitivity": "{{ form.motion_settings.sensitivity }}",
            "method": "{{ form.motion_settings.method }}"
          },
          "devices": [{
            "device_id": "{{ form.select_camera.camera_device.device_id }}",
            "name": "Motion: {{ form.select_camera.camera_device.extracted_data.name }}"
          }]
        }
      }
    ]
  }]
}
```

### Key Configuration Elements

**parasite_targets Array:**
```json
"config": {
  "parasite_targets": [{
    "mqtt_path": "{{ form.select_camera.camera_device.mqtt_path }}",
    "device_id": "{{ form.select_camera.camera_device.device_id }}",
    "instance_id": "{{ form.select_camera.camera_device.instance_id }}",
    "extracted_data": "{{ form.select_camera.camera_device.extracted_data }}"
  }]
}
```

**Device ID Inheritance:**
```json
"devices": [{
  "device_id": "{{ form.select_camera.camera_device.device_id }}"
}]
```

Device ID MUST match parent device for proper field association.

### Multi-Device Parasitic Connector

Extend multiple parent devices from single parasitic instance:

```json
{
  "flows": [{
    "id": "multi_device",
    "name": "Add Motion Detection (Multiple Cameras)",
    "steps": [
      {
        "id": "select_cameras",
        "type": "form",
        "title": "Select Cameras",
        "description": "Choose multiple cameras to monitor",
        "schema": {
          "fields": [{
            "type": "mqtt_device_picker",
            "name": "cameras",
            "label": "Cameras to Monitor",
            "required": true,
            "multiple": true,
            "config": {
              "connector_type": "cameras",
              "extract_fields": ["ip", "stream_urls.rtsp", "name"]
            }
          }]
        }
      },
      {
        "id": "create_instance",
        "type": "instance",
        "instance": {
          "connector_type": "cameras-motion",
          "config": {
            "parasite_targets": "{{ form.select_cameras.cameras }}",
            "sensitivity": 0.7
          },
          "devices": "{{ form.select_cameras.cameras | map_field('device_id', 'name') }}"
        }
      }
    ]
  }]
}
```

Note: The `map_field` template filter extracts device_id and name from picker results.

### MQTT Topic Results

After setup, parasitic connector publishes to dual namespaces:

**Own Instance (Control & Status):**
```
iot2mqtt/v1/instances/cameras_motion_abc123/devices/camera_1/state
→ {"online": true, "fps": 30, "status": "detecting"}

iot2mqtt/v1/instances/cameras_motion_abc123/devices/camera_1/cmd
→ Accepts: {"sensitivity": 0.9, "enabled": false}

iot2mqtt/v1/instances/cameras_motion_abc123/devices/camera_1/parasite
→ ["iot2mqtt/v1/instances/cameras_xyz/devices/camera_1"]
```

**Parent Instance (Extended Fields):**
```
iot2mqtt/v1/instances/cameras_xyz/devices/camera_1/state/motion → true
iot2mqtt/v1/instances/cameras_xyz/devices/camera_1/state/motion_confidence → 0.92
iot2mqtt/v1/instances/cameras_xyz/devices/camera_1/state/motion_last_detected → "..."
```

### Connector Implementation Requirements

Parasitic connectors must:

1. Inherit from `BaseConnector` (provides automatic parasite handling)
2. Use `self.publish_parasite_fields()` to extend parent devices
3. Use `self.get_parent_state()` to access parent device data
4. Implement `get_device_state()` returning own operational status
5. Implement `set_device_state()` handling own CMD topics

See [Parasitic Connectors Guide](parasitic-connectors.md) for implementation details.

## Backend Validation

`FlowSetupSchema` validates incoming JSON when `/api/integrations/{name}/meta`
fetches the schema. Request bodies submitted to `/api/instances` reuse the same
schema to ensure required fields are present and numeric bounds are respected.
Custom validation can be added by enriching the schema (e.g. `pattern` for form
fields); the backend mirrors these checks before writing the instance file.

## Frontend Behaviour

`FlowSetupForm` lives in `web/frontend/src/components/integrations/FlowSetupForm.tsx`:

- Renders flow selector tabs when multiple flows exist.
- Auto-runs tool steps marked with `auto_advance`.
- Throttles select-step state to prevent runaway re-renders.
- Converts numeric strings (e.g. ports, durations) to numbers before posting to
  `/api/instances`.
- Handles OAuth popups and stores sessions transparently.

Any future step types or actions can be implemented centrally in this component
without touching individual connector code.
