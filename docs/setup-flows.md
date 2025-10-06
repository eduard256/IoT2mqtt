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

When `instance_id` field is empty or set to `"auto"`, the frontend automatically
generates a unique identifier from the `friendly_name` field:

- Converts to lowercase
- Replaces spaces with underscores
- Removes special characters (keeps alphanumeric, underscores, hyphens)
- Collapses multiple underscores
- Trims leading/trailing underscores

Examples:
- `"Living Room Light"` → `"living_room_light"`
- `"My Device #1"` → `"my_device_1"`
- `"Test   Device"` → `"test_device"`

Users can override the auto-generated ID by entering a custom value in the
advanced section. The backend validates uniqueness and returns HTTP 409 if
an instance with the same ID already exists.

This feature is universal for all integrations and requires no connector-specific
code. To use it:

1. Mark the `instance_id` field as `"advanced": true`
2. Set `"placeholder": "auto"` to hint at auto-generation
3. Make it non-required or leave `"required": false` (default)
4. Ensure `friendly_name` appears before `instance_id` in the form

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
