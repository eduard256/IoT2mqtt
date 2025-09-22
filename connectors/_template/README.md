# Connector Template

This directory demonstrates the structure expected by the new declarative setup
flow system. Copy it to start a new integration and replace the placeholder
logic with real code.

## Files

- `setup.json` — declarative configuration describing setup flows, tools, and
  requirements.
- `actions/` — isolated scripts executed during setup (run inside the test
  runner container).
- `connector.py` — runtime implementation inheriting from
  `shared.base_connector.BaseConnector`.
- `Dockerfile` — build definition for the connector container.
- `requirements.txt` — Python dependencies used by runtime or actions.
- `main.py` — entry point launched in the connector container.

## Adding new steps

Update `setup.json` to describe additional flows, tools, or forms. The web UI
renders the JSON directly, so no frontend changes are required when onboarding a
new connector.
