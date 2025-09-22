import json
from pathlib import Path

from services.config_service import ConfigService


def test_save_instance_with_connection(setup_test_env):
    """Test that instance configuration saves connection data properly"""
    base = setup_test_env
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

    service.save_instance_config('sample', 'demo', instance_config)

    stored = json.loads((base / 'instances' / 'sample' / 'demo.json').read_text())
    assert stored['connection']['discovery_enabled'] is True
    assert stored['connection']['effect_type'] == 'smooth'
    assert 'instance_id' in stored
    assert 'created_at' in stored


def test_load_instance_config(setup_test_env):
    """Test loading instance configuration"""
    base = setup_test_env
    service = ConfigService(base_path=str(base))

    # Create instance first
    instance_config = {
        "instance_id": "test",
        "connector_type": "sample",
        "friendly_name": "Test Instance"
    }

    service.save_instance_config('sample', 'test', instance_config)

    # Load it back
    loaded = service.get_instance_config('sample', 'test')

    assert loaded is not None
    assert loaded['instance_id'] == 'test'
    assert loaded['connector_type'] == 'sample'


def test_list_connectors_empty(setup_test_env):
    """Test listing connectors when none exist"""
    base = setup_test_env
    service = ConfigService(base_path=str(base))

    connectors = service.list_connectors()
    assert connectors == []
