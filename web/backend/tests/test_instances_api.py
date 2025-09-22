"""
Tests for Instances API endpoints
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Import router lazily to avoid module-level initialization


class TestInstancesAPI:
    """Test Instances API endpoints"""

    @pytest.fixture
    def router(self, setup_test_env):
        """Import router with test environment"""
        from api.instances import router
        return router

    @pytest.fixture
    def app(self, router):
        """Create test FastAPI app"""
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_services(self):
        """Mock all services used by instances API"""
        with patch('api.instances.config_service') as mock_config, \
             patch('api.instances.docker_service') as mock_docker:
            yield {
                'config': mock_config,
                'docker': mock_docker
            }

    def test_list_instances_empty(self, client, mock_services):
        """Test listing instances when none exist"""
        mock_services['config'].list_instances.return_value = []

        response = client.get("/api/instances")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_instances_with_data(self, client, mock_services):
        """Test listing instances with container status"""
        instances = [
            {
                "instance_id": "test1",
                "connector_type": "yeelight",
                "friendly_name": "Test Light 1"
            },
            {
                "instance_id": "test2",
                "connector_type": "yeelight",
                "friendly_name": "Test Light 2"
            }
        ]

        mock_services['config'].list_instances.return_value = instances

        # Mock container info
        mock_container = Mock()
        mock_container.status = "running"
        mock_container.short_id = "abc123"

        mock_services['docker'].get_container.return_value = mock_container

        response = client.get("/api/instances")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["container_status"] == "running"
        assert data[0]["container_id"] == "abc123"

    def test_list_instances_no_container(self, client, mock_services):
        """Test listing instances when container doesn't exist"""
        instances = [
            {
                "instance_id": "test1",
                "connector_type": "yeelight",
                "friendly_name": "Test Light 1"
            }
        ]

        mock_services['config'].list_instances.return_value = instances
        mock_services['docker'].get_container.return_value = None

        response = client.get("/api/instances")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["container_status"] == "not_created"
        assert data[0]["container_id"] is None

    def test_get_instance_exists(self, client, mock_services):
        """Test getting specific instance"""
        instance_data = {
            "instance_id": "test1",
            "connector_type": "yeelight",
            "friendly_name": "Test Light"
        }

        mock_services['config'].load_instance_with_secrets.return_value = instance_data

        mock_container = Mock()
        mock_container.status = "running"
        mock_container.short_id = "abc123"
        mock_services['docker'].get_container.return_value = mock_container

        response = client.get("/api/instances/yeelight/test1")

        assert response.status_code == 200
        data = response.json()
        assert data["instance_id"] == "test1"
        assert data["container_status"] == "running"

    def test_get_instance_not_found(self, client, mock_services):
        """Test getting non-existent instance"""
        mock_services['config'].load_instance_with_secrets.return_value = None

        response = client.get("/api/instances/yeelight/nonexistent")

        assert response.status_code == 404

    def test_create_instance_success(self, client, mock_services):
        """Test successful instance creation"""
        mock_services['config'].get_instance_config.return_value = None  # Instance doesn't exist
        mock_services['config'].save_instance_with_secrets.return_value = {}
        mock_services['config'].load_docker_compose.return_value = {
            "version": "3.8",
            "services": {},
            "networks": {"iot2mqtt": {"driver": "bridge"}}
        }

        request_data = {
            "instance_id": "test_light",
            "connector_type": "yeelight",
            "friendly_name": "Test Light",
            "config": {
                "ip": "192.168.1.100",
                "discovery_enabled": True
            },
            "devices": [],
            "enabled": True
        }

        response = client.post("/api/instances", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["instance_id"] == "test_light"

        # Verify services were called
        mock_services['config'].save_instance_with_secrets.assert_called_once()
        mock_services['config'].save_docker_compose.assert_called_once()

    def test_create_instance_already_exists(self, client, mock_services):
        """Test creating instance that already exists"""
        mock_services['config'].get_instance_config.return_value = {
            "instance_id": "test_light"
        }

        request_data = {
            "instance_id": "test_light",
            "connector_type": "yeelight",
            "friendly_name": "Test Light",
            "config": {}
        }

        response = client.post("/api/instances", json=request_data)

        assert response.status_code == 409

    def test_create_instance_with_secrets(self, client, mock_services):
        """Test creating instance with secrets"""
        mock_services['config'].get_instance_config.return_value = None
        mock_services['config'].save_instance_with_secrets.return_value = {
            "secrets": {"test_credentials": {"file": "/path/to/secret"}},
            "service_secrets": [{"source": "test_credentials"}]
        }
        mock_services['config'].load_docker_compose.return_value = {
            "version": "3.8",
            "services": {},
            "networks": {"iot2mqtt": {"driver": "bridge"}}
        }

        request_data = {
            "instance_id": "test_light",
            "connector_type": "yeelight",
            "friendly_name": "Test Light",
            "config": {"ip": "192.168.1.100"},
            "secrets": {"api_key": "secret_key_123"}
        }

        response = client.post("/api/instances", json=request_data)

        assert response.status_code == 200

        # Verify secrets were passed
        call_args = mock_services['config'].save_instance_with_secrets.call_args
        assert call_args[1] == {"api_key": "secret_key_123"}  # explicit_secrets parameter

    def test_update_instance_success(self, client, mock_services):
        """Test successful instance update"""
        existing_instance = {
            "instance_id": "test_light",
            "connector_type": "yeelight",
            "friendly_name": "Old Name",
            "connection": {"ip": "192.168.1.100"},
            "enabled": True
        }

        mock_services['config'].load_instance_with_secrets.return_value = existing_instance
        mock_services['docker'].restart_container.return_value = True

        update_data = {
            "friendly_name": "New Name",
            "config": {"ip": "192.168.1.101", "brightness": 75},
            "enabled": False
        }

        response = client.put("/api/instances/yeelight/test_light", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify save was called
        mock_services['config'].save_instance_with_secrets.assert_called_once()

        # Verify container restart
        mock_services['docker'].restart_container.assert_called_once_with(
            "iot2mqtt_yeelight_test_light"
        )

    def test_update_instance_not_found(self, client, mock_services):
        """Test updating non-existent instance"""
        mock_services['config'].load_instance_with_secrets.return_value = None

        update_data = {"friendly_name": "New Name"}

        response = client.put("/api/instances/yeelight/nonexistent", json=update_data)

        assert response.status_code == 404

    def test_update_instance_restart_failed(self, client, mock_services):
        """Test update when container restart fails"""
        existing_instance = {
            "instance_id": "test_light",
            "connector_type": "yeelight",
            "friendly_name": "Test Light"
        }

        mock_services['config'].load_instance_with_secrets.return_value = existing_instance
        mock_services['docker'].restart_container.return_value = False

        update_data = {"friendly_name": "New Name"}

        response = client.put("/api/instances/yeelight/test_light", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["warning"] is True

    def test_delete_instance_success(self, client, mock_services):
        """Test successful instance deletion"""
        mock_container = Mock()
        mock_services['docker'].get_container.return_value = mock_container
        mock_services['docker'].stop_container.return_value = True
        mock_services['docker'].remove_container.return_value = True
        mock_services['config'].delete_instance_config.return_value = True

        compose_data = {
            "services": {
                "yeelight_test_light": {"image": "test"},
                "other_service": {"image": "other"}
            }
        }
        mock_services['config'].load_docker_compose.return_value = compose_data

        response = client.delete("/api/instances/yeelight/test_light")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify container operations
        mock_services['docker'].stop_container.assert_called_once()
        mock_services['docker'].remove_container.assert_called_once()

        # Verify config deletion
        mock_services['config'].delete_instance_config.assert_called_once_with(
            "yeelight", "test_light"
        )

    def test_delete_instance_not_found(self, client, mock_services):
        """Test deleting non-existent instance"""
        mock_services['docker'].get_container.return_value = None
        mock_services['config'].delete_instance_config.return_value = False

        response = client.delete("/api/instances/yeelight/nonexistent")

        assert response.status_code == 404

    def test_get_instance_errors_placeholder(self, client, mock_services):
        """Test getting instance errors (placeholder implementation)"""
        response = client.get("/api/instances/yeelight/test_light/errors")

        assert response.status_code == 200
        assert response.json() == []

    def test_retry_instance(self, client, mock_services):
        """Test retrying instance"""
        response = client.post("/api/instances/yeelight/test_light/retry")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Retry initiated"

    def test_create_instance_host_network_mode(self, client, mock_services):
        """Test creating instance with host network mode requirement"""
        mock_services['config'].get_instance_config.return_value = None
        mock_services['config'].save_instance_with_secrets.return_value = {}
        mock_services['config'].load_docker_compose.return_value = {
            "version": "3.8",
            "services": {},
            "networks": {"iot2mqtt": {"driver": "bridge"}}
        }

        # Mock connector setup with host network requirement
        mock_services['config'].get_connector_setup.return_value = {
            "requirements": {"network": "host"}
        }

        request_data = {
            "instance_id": "test_device",
            "connector_type": "network_connector",
            "friendly_name": "Network Device",
            "config": {}
        }

        response = client.post("/api/instances", json=request_data)

        assert response.status_code == 200

        # Verify save_docker_compose was called
        save_call = mock_services['config'].save_docker_compose.call_args[0][0]
        service_config = save_call["services"]["network_connector_test_device"]

        # Should have network_mode: host
        assert service_config["network_mode"] == "host"
        # Should not have networks key
        assert "networks" not in service_config

    @pytest.mark.asyncio
    async def test_create_and_start_container_background_task(self, mock_services):
        """Test background task for container creation"""
        from api.instances import create_and_start_container

        mock_services['docker'].create_container.return_value = "container_id_123"

        config = {"test": "config"}

        # Run background task
        await create_and_start_container("test_connector", "test_instance", config)

        # Verify container creation was attempted
        mock_services['docker'].create_container.assert_called_once_with(
            "test_connector", "test_instance", config
        )

    @pytest.mark.asyncio
    async def test_retry_container_with_backoff_success(self, mock_services):
        """Test retry container with backoff - success case"""
        from api.instances import retry_container_with_backoff

        mock_container = Mock()
        mock_container.status = "running"

        mock_services['docker'].restart_container.return_value = True
        mock_services['docker'].get_container.return_value = mock_container

        result = await retry_container_with_backoff("test_container", "test_instance", max_retries=1)

        assert result is True
        mock_services['docker'].restart_container.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_container_with_backoff_failure(self, mock_services):
        """Test retry container with backoff - failure case"""
        from api.instances import retry_container_with_backoff

        mock_services['docker'].restart_container.return_value = False

        result = await retry_container_with_backoff("test_container", "test_instance", max_retries=1)

        assert result is False
        assert mock_services['docker'].restart_container.call_count == 1

    def test_list_instances_with_connector_filter(self, client, mock_services):
        """Test listing instances filtered by connector"""
        mock_services['config'].list_instances.return_value = [
            {"instance_id": "test1", "connector_type": "yeelight"}
        ]

        response = client.get("/api/instances?connector=yeelight")

        assert response.status_code == 200
        mock_services['config'].list_instances.assert_called_once_with("yeelight")

    def test_create_instance_backward_compatibility(self, client, mock_services):
        """Test that connection fields are exposed at top level for backward compatibility"""
        mock_services['config'].get_instance_config.return_value = None
        mock_services['config'].save_instance_with_secrets.return_value = {}
        mock_services['config'].load_docker_compose.return_value = {
            "version": "3.8",
            "services": {},
            "networks": {"iot2mqtt": {"driver": "bridge"}}
        }

        request_data = {
            "instance_id": "test_light",
            "connector_type": "yeelight",
            "friendly_name": "Test Light",
            "config": {
                "ip": "192.168.1.100",
                "discovery_enabled": True,
                "effect_type": "smooth"
            }
        }

        response = client.post("/api/instances", json=request_data)

        assert response.status_code == 200

        # Check that save_instance_with_secrets was called with top-level fields
        call_args = mock_services['config'].save_instance_with_secrets.call_args[0][2]

        # Should have connection object
        assert "connection" in call_args
        assert call_args["connection"]["ip"] == "192.168.1.100"

        # Should also have top-level fields for backward compatibility
        assert call_args["ip"] == "192.168.1.100"
        assert call_args["discovery_enabled"] is True
        assert call_args["effect_type"] == "smooth"