import json
from pathlib import Path

from services.config_service import ConfigService


def test_save_instance_merges_connection(tmp_path):
    base = tmp_path
    (base / 'connectors').mkdir(parents=True, exist_ok=True)
    service = ConfigService(base_path=str(base))

    instance_config = {
        "instance_id": "demo",
        "instance_type": "device",
        "connector_type": "sample",
        "friendly_name": "Sample",
        "connection": {"discovery_enabled": True, "effect_type": "smooth"},
        "devices": [],
        "enabled": True,
        "update_interval": 10
    }

    service.save_instance_with_secrets('sample', 'demo', instance_config)

    stored = json.loads((base / 'instances' / 'sample' / 'demo.json').read_text())
    assert stored['connection']['discovery_enabled'] is True
    # Keys from connection should also be exposed at root level for backwards compatibility
    assert stored['discovery_enabled'] is True
    assert stored['effect_type'] == 'smooth'
