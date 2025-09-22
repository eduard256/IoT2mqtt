"""
Extended tests for ConfigService
"""

import json
import os
import yaml
from pathlib import Path
from unittest.mock import patch, Mock

import pytest

from services.config_service import ConfigService


class TestConfigServiceExtended:
    """Extended tests for ConfigService functionality"""

    def test_detect_base_path_with_env_var(self, tmp_path, monkeypatch):
        """Test base path detection with environment variable"""
        test_path = tmp_path / "custom_path"
        test_path.mkdir()
        monkeypatch.setenv("IOT2MQTT_PATH", str(test_path))

        service = ConfigService()
        assert service.base_path == test_path

    def test_detect_base_path_with_docker_compose(self, tmp_path):
        """Test base path detection by finding docker-compose.yml"""
        # Create nested directory structure
        nested_path = tmp_path / "nested" / "backend"
        nested_path.mkdir(parents=True)

        # Create docker-compose.yml in root
        docker_compose = tmp_path / "docker-compose.yml"
        docker_compose.write_text("version: '3.8'")

        # Initialize from nested path
        with patch('pathlib.Path.cwd', return_value=nested_path):
            with patch('services.config_service.Path') as mock_path:
                # Mock __file__ to point to nested location
                mock_path(__file__).resolve.return_value = nested_path / "config_service.py"
                service = ConfigService()

        # Should find the root path with docker-compose.yml
        assert str(service.base_path).endswith(str(tmp_path.name))

    def test_save_and_load_env_vars(self, setup_test_env):
        """Test saving and loading environment variables"""
        service = ConfigService(base_path=str(setup_test_env))

        env_vars = {
            "MQTT_HOST": "broker.example.com",
            "MQTT_PORT": "1883",
            "WEB_PORT": "8765"
        }

        service.save_env(env_vars)

        # Load back
        loaded = service.load_env()

        assert loaded["MQTT_HOST"] == "broker.example.com"
        assert loaded["MQTT_PORT"] == "1883"
        assert loaded["WEB_PORT"] == "8765"

    def test_save_env_merge_existing(self, setup_test_env):
        """Test saving environment variables with merge"""
        service = ConfigService(base_path=str(setup_test_env))

        # Save initial vars
        initial_vars = {
            "MQTT_HOST": "localhost",
            "MQTT_PORT": "1883"
        }
        service.save_env(initial_vars)

        # Save additional vars with merge
        additional_vars = {
            "MQTT_PORT": "8883",  # Should update
            "WEB_PORT": "8765"    # Should add
        }
        service.save_env(additional_vars, merge=True)

        loaded = service.load_env()
        assert loaded["MQTT_HOST"] == "localhost"  # Unchanged
        assert loaded["MQTT_PORT"] == "8883"      # Updated
        assert loaded["WEB_PORT"] == "8765"       # Added

    def test_access_key_management(self, setup_test_env):
        """Test access key get/set operations"""
        service = ConfigService(base_path=str(setup_test_env))

        # Initially no key
        assert service.get_access_key() is None

        # Set key
        hashed_key = "hashed_password_123"
        service.set_access_key(hashed_key)

        # Get key back
        assert service.get_access_key() == hashed_key

    def test_mqtt_config_management(self, setup_test_env):
        """Test MQTT configuration management"""
        service = ConfigService(base_path=str(setup_test_env))

        mqtt_config = {
            "host": "mqtt.example.com",
            "port": 8883,
            "username": "mqtt_user",
            "password": "mqtt_pass",
            "base_topic": "MyIoT",
            "qos": 2,
            "retain": False
        }

        service.save_mqtt_config(mqtt_config)

        # Load back
        loaded = service.get_mqtt_config()

        assert loaded["host"] == "mqtt.example.com"
        assert loaded["port"] == 8883
        assert loaded["username"] == "mqtt_user"
        assert loaded["password"] == "mqtt_pass"
        assert loaded["base_topic"] == "MyIoT"
        assert loaded["qos"] == 2
        assert loaded["retain"] is False

    def test_list_connectors_with_setup(self, setup_test_env):
        """Test listing connectors with setup.json files"""
        service = ConfigService(base_path=str(setup_test_env))

        # Create connector with setup.json
        connector_dir = setup_test_env / "connectors" / "test_connector"
        connector_dir.mkdir(parents=True)

        setup_data = {
            "display_name": "Test Connector",
            "description": "A test connector",
            "version": "1.0.0"
        }

        setup_file = connector_dir / "setup.json"
        setup_file.write_text(json.dumps(setup_data))

        # Create icon file
        icon_file = connector_dir / "icon.svg"
        icon_file.write_text("<svg>test</svg>")

        connectors = service.list_connectors()

        assert len(connectors) == 1
        connector = connectors[0]
        assert connector["name"] == "test_connector"
        assert connector["display_name"] == "Test Connector"
        assert connector["description"] == "A test connector"
        assert connector["version"] == "1.0.0"
        assert connector["has_setup"] is True
        assert connector["has_icon"] is True

    def test_list_connectors_ignores_template(self, setup_test_env):
        """Test that _template connector is ignored"""
        service = ConfigService(base_path=str(setup_test_env))

        # Create _template connector
        template_dir = setup_test_env / "connectors" / "_template"
        template_dir.mkdir(parents=True)

        # Create regular connector
        connector_dir = setup_test_env / "connectors" / "real_connector"
        connector_dir.mkdir(parents=True)

        connectors = service.list_connectors()

        assert len(connectors) == 1
        assert connectors[0]["name"] == "real_connector"

    def test_instance_with_devices(self, setup_test_env):
        """Test instance management with devices list"""
        service = ConfigService(base_path=str(setup_test_env))

        instance_config = {
            "instance_id": "test_instance",
            "connector_type": "test_connector",
            "friendly_name": "Test Instance",
            "devices": [
                {"id": "device1", "name": "Device 1"},
                {"id": "device2", "name": "Device 2"}
            ]
        }

        service.save_instance_config("test_connector", "test_instance", instance_config)

        loaded = service.get_instance_config("test_connector", "test_instance")

        assert loaded is not None
        assert len(loaded["devices"]) == 2
        assert loaded["devices"][0]["id"] == "device1"

    def test_list_instances_by_connector(self, setup_test_env):
        """Test listing instances filtered by connector"""
        service = ConfigService(base_path=str(setup_test_env))

        # Create instances for different connectors
        config1 = {"instance_id": "inst1", "connector_type": "connector1"}
        config2 = {"instance_id": "inst2", "connector_type": "connector1"}
        config3 = {"instance_id": "inst3", "connector_type": "connector2"}

        service.save_instance_config("connector1", "inst1", config1)
        service.save_instance_config("connector1", "inst2", config2)
        service.save_instance_config("connector2", "inst3", config3)

        # List all instances
        all_instances = service.list_instances()
        assert len(all_instances) == 3

        # List instances for connector1
        connector1_instances = service.list_instances("connector1")
        assert len(connector1_instances) == 2
        assert all(i["connector_type"] == "connector1" for i in connector1_instances)

    def test_delete_instance_creates_backup(self, setup_test_env):
        """Test that deleting instance creates backup"""
        service = ConfigService(base_path=str(setup_test_env))

        # Create instance
        config = {"instance_id": "test", "connector_type": "test_connector"}
        service.save_instance_config("test_connector", "test", config)

        # Delete instance
        result = service.delete_instance_config("test_connector", "test")

        assert result is True

        # Check backup was created
        backup_dir = setup_test_env / "instances" / "test_connector" / ".backup"
        assert backup_dir.exists()

        backup_files = list(backup_dir.glob("test_*.json"))
        assert len(backup_files) == 1

    def test_load_save_docker_compose(self, setup_test_env):
        """Test docker-compose.yml management"""
        service = ConfigService(base_path=str(setup_test_env))

        compose_data = {
            "version": "3.8",
            "services": {
                "web": {
                    "image": "nginx",
                    "ports": ["80:80"]
                }
            },
            "networks": {
                "iot2mqtt": {"driver": "bridge"}
            }
        }

        service.save_docker_compose(compose_data)

        loaded = service.load_docker_compose()

        assert loaded["version"] == "3.8"
        assert "web" in loaded["services"]
        assert loaded["services"]["web"]["image"] == "nginx"

    def test_load_docker_compose_missing_file(self, setup_test_env):
        """Test loading docker-compose.yml when file doesn't exist"""
        service = ConfigService(base_path=str(setup_test_env))

        compose_data = service.load_docker_compose()

        # Should return default structure
        assert compose_data["version"] == "3.8"
        assert "services" in compose_data
        assert "networks" in compose_data

    def test_connector_setup_schema(self, setup_test_env):
        """Test getting connector setup schema"""
        service = ConfigService(base_path=str(setup_test_env))

        # Create connector with setup schema
        connector_dir = setup_test_env / "connectors" / "test_connector"
        connector_dir.mkdir(parents=True)

        setup_data = {
            "display_name": "Test Connector",
            "flows": [
                {
                    "id": "manual_setup",
                    "name": "Manual Setup",
                    "steps": []
                }
            ]
        }

        setup_file = connector_dir / "setup.json"
        setup_file.write_text(json.dumps(setup_data))

        schema = service.get_connector_setup("test_connector")

        assert schema is not None
        assert schema["display_name"] == "Test Connector"
        assert len(schema["flows"]) == 1

        # Test non-existent connector
        schema = service.get_connector_setup("nonexistent")
        assert schema is None

    def test_connector_branding(self, setup_test_env):
        """Test connector branding information"""
        service = ConfigService(base_path=str(setup_test_env))

        # Create connector with branding in setup
        connector_dir = setup_test_env / "connectors" / "test_connector"
        connector_dir.mkdir(parents=True)

        setup_data = {
            "branding": {
                "icon": "/custom/icon.svg",
                "color": "#ff0000",
                "background": "linear-gradient(red, blue)",
                "category": "lighting"
            }
        }

        setup_file = connector_dir / "setup.json"
        setup_file.write_text(json.dumps(setup_data))

        branding = service.get_connector_branding("test_connector")

        assert branding["icon"] == "/custom/icon.svg"
        assert branding["color"] == "#ff0000"
        assert branding["category"] == "lighting"

    def test_connector_branding_defaults(self, setup_test_env):
        """Test default connector branding when not specified"""
        service = ConfigService(base_path=str(setup_test_env))

        branding = service.get_connector_branding("nonexistent_connector")

        assert branding["color"] == "#6366F1"
        assert branding["category"] == "general"
        assert "default-icon.svg" in branding["icon"]

    def test_save_instance_with_secrets_separation(self, setup_test_env):
        """Test saving instance with secrets separation"""
        service = ConfigService(base_path=str(setup_test_env))

        config = {
            "instance_id": "test",
            "connector_type": "test_connector",
            "api_key": "secret_key_123",
            "password": "secret_password",
            "normal_setting": "public_value"
        }

        secrets = {"custom_secret": "custom_value"}

        result = service.save_instance_with_secrets(
            "test_connector", "test", config, secrets
        )

        # Should return Docker secret configuration
        assert "secrets" in result or result == {}

        # Load back with secrets
        loaded = service.load_instance_with_secrets("test_connector", "test")

        assert loaded is not None
        assert loaded["api_key"] == "secret_key_123"
        assert loaded["password"] == "secret_password"
        assert loaded["normal_setting"] == "public_value"

    def test_file_locking_context(self, setup_test_env):
        """Test file locking context manager"""
        service = ConfigService(base_path=str(setup_test_env))

        test_file = setup_test_env / "test_lock.txt"

        with service.locked_file(test_file, 'w') as f:
            f.write("test content")

        # File should exist and contain content
        assert test_file.exists()
        assert test_file.read_text() == "test content"

    def test_locked_json_file_context(self, setup_test_env):
        """Test locked JSON file context manager"""
        service = ConfigService(base_path=str(setup_test_env))

        test_file = setup_test_env / "test.json"

        # Create initial data
        with service.locked_json_file(test_file) as container:
            container['data'] = {"key": "value", "number": 42}

        # Read back
        with service.locked_json_file(test_file) as container:
            data = container['data']
            assert data["key"] == "value"
            assert data["number"] == 42

            # Modify data
            container['data']["new_key"] = "new_value"

        # Verify modification persisted
        loaded_data = json.loads(test_file.read_text())
        assert loaded_data["new_key"] == "new_value"