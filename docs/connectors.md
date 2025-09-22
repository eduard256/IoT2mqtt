# Connector Structure

Connectors now live entirely inside `connectors/<name>/` and expose their setup
flows via a declarative `setup.json`. The runtime containers mount shared code
from `/app/shared` and instance configuration from the top-level `instances/`
directory.

## Directory Layout

```
connectors/
  <connector_name>/
    actions/             # Setup flow helpers executed by the test-runner
    connector.py         # Runtime implementation (inherits BaseConnector)
    Dockerfile           # Builds iot2mqtt_<connector>:latest
    main.py              # Entrypoint for the container
    manifest.json        # Metadata for the integrations catalog
    requirements.txt     # Python dependencies for runtime/actions
    setup.json           # Declarative flow definition consumed by the web UI
    README.md            # Optional connector-specific notes
```

All instance files are stored under `instances/<connector>/<instance_id>.json`
and are never committed to the repository.

## Declarative Setup (`setup.json`)

The web UI reads `setup.json` and renders multi-step flows without any custom
frontend code. The schema is defined by `FlowSetupSchema` and includes:

- `flows` — list of scenarios (cloud, manual, discovery, etc.) with ordered
  `steps`.
- Step types: `form`, `tool`, `select`, `summary`, `message`, `oauth`,
  `instance`.
- `tools` — mapping of tool identifiers to scripts under `actions/`. Tools run
  inside the dedicated test-runner container.
- Optional metadata (`branding`, `requirements`, `discovery`) to enrich the
  integrations catalog.

### Step Data Binding

Templating uses double curly braces (e.g. `{{ form.credentials.username }}`)
with the following namespaces:

- `form.<step_id>` – values collected in previous form steps
- `tools.<output_key>` – JSON returned by tool executions
- `selection.<key>` – value produced by `select` steps
- `oauth.<provider>` – session information returned by OAuth flows
- `integration` – basic metadata such as the integration name

Arrays and objects can be produced by specifying structured `item_value`
objects or `instance` payloads – `FlowSetupForm` resolves nested placeholders
recursively.

## Runtime Containers

When an instance is created the backend:

1. Saves configuration to `instances/<connector>/<instance_id>.json`.
2. Extracts sensitive fields via `SecretsManager` and stores them under
   `secrets/instances/` (also exposed as Docker secrets to the container).
3. Updates `docker-compose.yml` with a service named
   `<connector>_<instance_id>` mounting `./instances/<connector>:/app/instances`.
4. Builds and starts `iot2mqtt_<connector>:latest` if necessary.

At runtime the connector uses `BaseConnector` which already handles MQTT
subscriptions, state publishing, and clean shutdown.

## Actions & Test Runner

Tool scripts under `actions/` run inside `test-runner`. Each script must read
JSON input from `stdin` (or accept `--` arguments) and print a JSON response to
`stdout` in the format `{ "ok": true/false, "result": ... }`.

Examples:

- `actions/discover.py` — scan the network and return device candidates.
- `actions/validate.py` — verify credentials or reachable hosts.
- `actions/autogen.py` — generate instance IDs, device names, or other helper
  data.

## Template Connector

A ready-to-clone template is available in `connectors/_template`. It contains a
minimal runtime, sample action, and a one-step `setup.json` to demonstrate the
shape of a flow. Copy the folder, rename it, and adjust the files to build new
integrations.
