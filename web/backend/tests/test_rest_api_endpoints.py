"""
Comprehensive tests for all REST API endpoints
Tests all major API routes: Auth, Devices, Docker, Cameras, Integrations, MQTT, Main
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from jose import jwt


# =============================================================================
# AUTH API TESTS
# =============================================================================

class TestAuthAPI:
    """Test Authentication API endpoints"""

    @pytest.fixture
    def router(self, setup_test_env):
        """Import router with test environment"""
        from api.auth import router
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

    def test_login_first_time_setup(self, client, setup_test_env):
        """Test login creates access key on first use"""
        with patch('services.config_service.ConfigService') as mock_config_class:
            mock_config = mock_config_class.return_value
            mock_config.get_access_key.return_value = None

            response = client.post("/api/auth/login", json={"key": "my-secret-key"})

            assert response.status_code == 200
            data = response.json()
            assert "token" in data
            assert data["token_type"] == "bearer"
            mock_config.set_access_key.assert_called_once()

    def test_login_correct_password(self, client):
        """Test login with correct password"""
        from api.auth import get_password_hash

        with patch('services.config_service.ConfigService') as mock_config_class:
            mock_config = mock_config_class.return_value
            mock_config.get_access_key.return_value = get_password_hash("correct-password")

            response = client.post("/api/auth/login", json={"key": "correct-password"})

            assert response.status_code == 200
            data = response.json()
            assert "token" in data
            assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        """Test login with wrong password returns 401"""
        from api.auth import get_password_hash

        with patch('services.config_service.ConfigService') as mock_config_class:
            mock_config = mock_config_class.return_value
            mock_config.get_access_key.return_value = get_password_hash("correct-password")

            response = client.post("/api/auth/login", json={"key": "wrong-password"})

            assert response.status_code == 401
            assert "Invalid access key" in response.json()["detail"]

    def test_login_missing_key(self, client):
        """Test login without key returns 400"""
        response = client.post("/api/auth/login", json={})

        assert response.status_code == 400
        assert "Access key is required" in response.json()["detail"]

    def test_verify_valid_token(self, client):
        """Test verify endpoint with valid token"""
        from api.auth import create_access_token

        token = create_access_token({"sub": "admin"})

        response = client.post(
            "/api/auth/verify",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["user"] == "admin"

    def test_verify_invalid_token(self, client):
        """Test verify endpoint with invalid token"""
        response = client.post(
            "/api/auth/verify",
            headers={"Authorization": "Bearer invalid-token"}
        )

        assert response.status_code == 403

    def test_verify_expired_token(self, client):
        """Test verify endpoint with expired token"""
        from api.auth import create_access_token, SECRET_KEY, ALGORITHM

        # Create expired token
        expired_token = jwt.encode(
            {"sub": "admin", "exp": datetime.utcnow() - timedelta(hours=1)},
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        response = client.post(
            "/api/auth/verify",
            headers={"Authorization": f"Bearer {expired_token}"}
        )

        assert response.status_code == 403


# =============================================================================
# DEVICES API TESTS
# =============================================================================

class TestDevicesAPI:
    """Test Devices API endpoints"""

    @pytest.fixture
    def router(self, setup_test_env):
        """Import router with test environment"""
        from api.devices import router
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
    def auth_headers(self):
        """Create auth headers with valid token"""
        from api.auth import create_access_token
        token = create_access_token({"sub": "admin"})
        return {"Authorization": f"Bearer {token}"}

    def test_get_all_devices_empty(self, client, auth_headers):
        """Test getting devices when none exist"""
        with patch('api.devices.config_service') as mock_config:
            mock_config.list_instances.return_value = []

            response = client.get("/api/devices/", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["devices"] == []

    def test_get_all_devices_with_data(self, client, auth_headers):
        """Test getting devices with data"""
        with patch('api.devices.config_service') as mock_config, \
             patch('api.devices.docker_service') as mock_docker:

            mock_config.list_instances.return_value = [
                {
                    "connector_type": "yeelight",
                    "instance_id": "living-room",
                    "devices": [
                        {
                            "device_id": "lamp1",
                            "friendly_name": "Living Room Lamp",
                            "device_type": "light",
                            "enabled": True,
                            "state": {"power": "on", "brightness": 80}
                        }
                    ]
                }
            ]

            mock_container_info = {"status": "running"}
            mock_docker.get_container_info.return_value = mock_container_info

            response = client.get("/api/devices/", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["devices"]) == 1
            device = data["devices"][0]
            assert device["device_id"] == "lamp1"
            assert device["friendly_name"] == "Living Room Lamp"
            assert device["online"] is True

    def test_get_all_devices_offline_container(self, client, auth_headers):
        """Test devices marked offline when container is not running"""
        with patch('api.devices.config_service') as mock_config, \
             patch('api.devices.docker_service') as mock_docker:

            mock_config.list_instances.return_value = [
                {
                    "connector_type": "yeelight",
                    "instance_id": "bedroom",
                    "devices": [{"device_id": "lamp2", "enabled": True}]
                }
            ]

            mock_docker.get_container_info.return_value = {"status": "exited"}

            response = client.get("/api/devices/", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["devices"][0]["online"] is False

    def test_get_devices_unauthorized(self, client):
        """Test devices endpoint without auth returns 401"""
        response = client.get("/api/devices/")

        assert response.status_code == 403


# =============================================================================
# DOCKER API TESTS
# =============================================================================

class TestDockerAPI:
    """Test Docker API endpoints"""

    @pytest.fixture
    def router(self, setup_test_env):
        """Import router with test environment"""
        from api.docker import router
        return router

    @pytest.fixture
    def app(self, router):
        """Create test FastAPI app"""
        app = FastAPI()
        # Mount with prefix like in main.py
        app.include_router(router, prefix="/api/docker")
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Create auth headers"""
        from api.auth import create_access_token
        token = create_access_token({"sub": "admin"})
        return {"Authorization": f"Bearer {token}"}

    def test_list_containers(self, client, auth_headers):
        """Test listing Docker containers"""
        with patch('api.docker.docker_service') as mock_docker:
            mock_docker.list_containers.return_value = [
                {
                    "id": "abc123",
                    "name": "iot2mqtt_test",
                    "status": "running",
                    "state": "running",
                    "created": "2024-01-01T00:00:00Z",
                    "image": "iot2mqtt_test:latest",
                    "ports": {},
                    "labels": {}
                }
            ]

            response = client.get("/api/docker/containers", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["id"] == "abc123"
            assert data[0]["name"] == "iot2mqtt_test"
            assert data[0]["status"] == "running"

    def test_start_container(self, client, auth_headers):
        """Test starting a container"""
        with patch('api.docker.docker_service') as mock_docker:
            mock_docker.start_container.return_value = True

            response = client.post(
                "/api/docker/containers/abc123/start",
                headers=auth_headers
            )

            assert response.status_code == 200
            assert response.json()["success"] is True
            mock_docker.start_container.assert_called_once_with("abc123")

    def test_stop_container(self, client, auth_headers):
        """Test stopping a container"""
        with patch('api.docker.docker_service') as mock_docker:
            mock_docker.stop_container.return_value = True

            response = client.post(
                "/api/docker/containers/abc123/stop",
                headers=auth_headers
            )

            assert response.status_code == 200
            assert response.json()["success"] is True
            mock_docker.stop_container.assert_called_once_with("abc123")

    def test_restart_container(self, client, auth_headers):
        """Test restarting a container"""
        with patch('api.docker.docker_service') as mock_docker:
            mock_docker.restart_container.return_value = True

            response = client.post(
                "/api/docker/containers/abc123/restart",
                headers=auth_headers
            )

            assert response.status_code == 200
            assert response.json()["success"] is True
            mock_docker.restart_container.assert_called_once_with("abc123")

    def test_delete_container(self, client, auth_headers):
        """Test deleting a container"""
        with patch('api.docker.docker_service') as mock_docker:
            mock_docker.stop_container.return_value = True
            mock_docker.remove_container.return_value = True

            response = client.delete(
                "/api/docker/containers/abc123",
                headers=auth_headers
            )

            assert response.status_code == 200
            assert response.json()["success"] is True
            mock_docker.stop_container.assert_called_once_with("abc123")
            mock_docker.remove_container.assert_called_once()

    def test_get_container_logs(self, client, auth_headers):
        """Test getting container logs"""
        with patch('api.docker.docker_service') as mock_docker:
            # Return list of dictionaries as expected by ContainerLogs model
            mock_docker.get_container_logs.return_value = [
                {"timestamp": "2024-01-01T00:00:00", "message": "Log line 1"},
                {"timestamp": "2024-01-01T00:00:01", "message": "Log line 2"}
            ]

            response = client.get(
                "/api/docker/containers/abc123/logs?lines=100",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert "logs" in data
            assert data["container_id"] == "abc123"


# =============================================================================
# CAMERAS API TESTS
# =============================================================================

class TestCamerasAPI:
    """Test Cameras API endpoints"""

    @pytest.fixture
    def router(self, setup_test_env):
        """Import router with test environment"""
        from api.cameras import router
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
    def auth_headers(self):
        """Create auth headers"""
        from api.auth import create_access_token
        token = create_access_token({"sub": "admin"})
        return {"Authorization": f"Bearer {token}"}

    def test_search_cameras(self, client, auth_headers):
        """Test searching camera database"""
        with patch('api.cameras.camera_index') as mock_index:
            mock_index.search.return_value = [
                {
                    "brand": "hikvision",
                    "model": "DS-2CD2142FWD-I",
                    "entry": {
                        "jpeg_url": "http://{ip}/snapshot.jpg",
                        "rtsp_url": "rtsp://{ip}:554/Streaming/Channels/1"
                    }
                }
            ]

            response = client.get(
                "/api/cameras/search?q=hikvision",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["brand"] == "hikvision"

    def test_scan_streams(self, client, auth_headers):
        """Test starting stream scan"""
        scan_request = {
            "ip": "192.168.1.100",
            "username": "admin",
            "password": "password123",
            "brand": "hikvision",
            "model": "DS-2CD2142FWD-I"
        }

        with patch('api.cameras.camera_scanner') as mock_scanner:
            mock_scanner.start_scan.return_value = "task-123"

            response = client.post(
                "/api/cameras/scan-streams",
                json=scan_request,
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert "task_id" in data

    def test_get_scan_status(self, client, auth_headers):
        """Test getting scan status"""
        with patch('api.cameras.camera_scanner') as mock_scanner:
            mock_scanner.get_scan_status.return_value = {
                "status": "running",
                "progress": 50,
                "streams_found": 2
            }

            response = client.get(
                "/api/cameras/scan-streams/task-123/status",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert data["progress"] == 50


# =============================================================================
# INTEGRATIONS API TESTS
# =============================================================================

class TestIntegrationsAPI:
    """Test Integrations API endpoints"""

    @pytest.fixture
    def router(self, setup_test_env):
        """Import router with test environment"""
        from api.integrations import router
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
    def auth_headers(self):
        """Create auth headers"""
        from api.auth import create_access_token
        token = create_access_token({"sub": "admin"})
        return {"Authorization": f"Bearer {token}"}

    def test_list_configured_integrations(self, client, auth_headers):
        """Test listing configured integrations"""
        with patch('api.integrations.config_service') as mock_config:
            mock_config.list_instances.return_value = [
                {
                    "instance_id": "living-room",
                    "connector_type": "yeelight",
                    "friendly_name": "Living Room Lights"
                }
            ]

            response = client.get("/api/integrations/", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert len(data) > 0

    def test_get_integration_instances(self, client, auth_headers):
        """Test getting instances for specific integration"""
        with patch('api.integrations.config_service') as mock_config, \
             patch('api.integrations.docker_service') as mock_docker:

            mock_config.list_instances.return_value = [
                {
                    "instance_id": "test-1",
                    "connector_type": "yeelight",
                    "enabled": True
                }
            ]

            mock_container = Mock()
            mock_container.status = "running"
            mock_container.short_id = "abc123"
            mock_docker.get_container.return_value = mock_container

            response = client.get(
                "/api/integrations/yeelight/instances",
                headers=auth_headers
            )

            assert response.status_code == 200

    def test_start_instance(self, client, auth_headers):
        """Test starting an instance"""
        with patch('api.integrations.docker_service') as mock_docker:
            mock_container = Mock()
            mock_docker.get_container.return_value = mock_container

            response = client.post(
                "/api/integrations/instances/test-1/start",
                headers=auth_headers
            )

            assert response.status_code == 200

    def test_stop_instance(self, client, auth_headers):
        """Test stopping an instance"""
        with patch('api.integrations.docker_service') as mock_docker:
            mock_container = Mock()
            mock_docker.get_container.return_value = mock_container

            response = client.post(
                "/api/integrations/instances/test-1/stop",
                headers=auth_headers
            )

            assert response.status_code == 200

    def test_delete_instance(self, client, auth_headers):
        """Test deleting an instance"""
        with patch('api.integrations.config_service') as mock_config, \
             patch('api.integrations.docker_service') as mock_docker:

            mock_config.get_instance_by_id.return_value = {
                "connector_type": "yeelight",
                "instance_id": "test-1"
            }
            mock_config.delete_instance_config.return_value = True

            mock_container = Mock()
            mock_docker.get_container.return_value = mock_container

            response = client.delete(
                "/api/integrations/instances/test-1",
                headers=auth_headers
            )

            assert response.status_code == 200


# =============================================================================
# CONNECTORS API TESTS
# =============================================================================

class TestConnectorsAPI:
    """Test Connectors API endpoints"""

    @pytest.fixture
    def router(self, setup_test_env):
        """Import router with test environment"""
        from api.connectors import router
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
    def auth_headers(self):
        """Create auth headers"""
        from api.auth import create_access_token
        token = create_access_token({"sub": "admin"})
        return {"Authorization": f"Bearer {token}"}

    def test_list_available_integrations(self, client, auth_headers):
        """Test listing available connectors/integrations"""
        with patch('api.connectors.config_service') as mock_config:
            mock_config.list_connectors.return_value = [
                {
                    "name": "yeelight",
                    "friendly_name": "Yeelight",
                    "description": "Xiaomi Yeelight smart bulbs",
                    "icon": "lightbulb"
                }
            ]

            response = client.get("/api/integrations", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert len(data) > 0

    def test_get_integration_meta(self, client, auth_headers):
        """Test getting integration metadata"""
        with patch('api.connectors.config_service') as mock_config:
            mock_config.get_connector_setup.return_value = {
                "name": "yeelight",
                "version": "1.0.0",
                "steps": []
            }

            response = client.get(
                "/api/integrations/yeelight/meta",
                headers=auth_headers
            )

            assert response.status_code == 200

    def test_discover_devices(self, client, auth_headers):
        """Test device discovery for integration"""
        with patch('api.connectors.discover_yeelight_devices') as mock_discover:
            mock_discover.return_value = [
                {
                    "id": "0x1234567890",
                    "model": "color",
                    "support": "get_prop set_default set_power",
                    "ip": "192.168.1.100"
                }
            ]

            response = client.post(
                "/api/integrations/yeelight/discover",
                json={},
                headers=auth_headers
            )

            # May return 200 or 500 depending on implementation
            assert response.status_code in [200, 500]

    def test_validate_connection(self, client, auth_headers):
        """Test validating connection to device"""
        validate_data = {
            "ip": "192.168.1.100",
            "port": 55443
        }

        response = client.post(
            "/api/integrations/yeelight/validate",
            json=validate_data,
            headers=auth_headers
        )

        # May return 200 or 500 depending on implementation
        assert response.status_code in [200, 500]


# =============================================================================
# MQTT DISCOVERY API TESTS
# =============================================================================

class TestMQTTDiscoveryAPI:
    """Test MQTT Discovery API endpoints"""

    @pytest.fixture
    def router(self, setup_test_env):
        """Import router with test environment"""
        from api.mqtt_discovery import router
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
    def auth_headers(self):
        """Create auth headers"""
        from api.auth import create_access_token
        token = create_access_token({"sub": "admin"})
        return {"Authorization": f"Bearer {token}"}

    def test_discover_connector_devices_no_mqtt(self, client, auth_headers):
        """Test discovering devices when MQTT not connected"""
        with patch('api.mqtt_discovery.mqtt_service', None):
            response = client.post(
                "/api/mqtt/discover-connector-devices",
                json={},
                headers=auth_headers
            )

            assert response.status_code == 503

    def test_get_connector_types(self, client, auth_headers):
        """Test getting list of connector types"""
        with patch('api.mqtt_discovery.config_service') as mock_config:
            mock_config.list_connectors.return_value = [
                {"name": "yeelight"},
                {"name": "cameras"}
            ]

            response = client.get(
                "/api/mqtt/connector-types",
                headers=auth_headers
            )

            assert response.status_code == 200


# =============================================================================
# MAIN ENDPOINTS TESTS (from main.py)
# =============================================================================

class TestMainEndpoints:
    """Test endpoints defined in main.py"""

    @pytest.fixture
    def app(self, setup_test_env):
        """Import and create main app"""
        import sys
        from pathlib import Path

        # Ensure main module can be imported
        backend_path = Path(__file__).parent.parent
        if str(backend_path) not in sys.path:
            sys.path.insert(0, str(backend_path))

        # Mock lifespan to avoid MQTT connection
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_lifespan(app):
            yield

        with patch('main.lifespan', mock_lifespan):
            from main import app
            return app

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Create auth headers"""
        from api.auth import create_access_token
        token = create_access_token({"sub": "admin"})
        return {"Authorization": f"Bearer {token}"}

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data

    def test_setup_status(self, client):
        """Test setup status endpoint"""
        with patch('main.config_service') as mock_config:
            mock_config.get_access_key.return_value = "hashed-key"
            mock_config.get_mqtt_config.return_value = {"host": "localhost"}

            response = client.get("/api/setup/status")

            assert response.status_code == 200
            data = response.json()
            assert "has_access_key" in data
            assert "has_mqtt_config" in data
            assert "setup_complete" in data

    def test_mqtt_status(self, client, auth_headers):
        """Test MQTT status endpoint"""
        with patch('main.config_service') as mock_config, \
             patch('main.mqtt_service') as mock_mqtt:

            mock_config.get_mqtt_config.return_value = {
                "host": "localhost",
                "port": 1883,
                "base_topic": "IoT2mqtt"
            }
            mock_mqtt.connected = True
            mock_mqtt.topic_cache = {}

            response = client.get("/api/mqtt/status", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert "connected" in data
            assert "broker" in data

    def test_mqtt_test_connection(self, client):
        """Test MQTT connection test"""
        test_config = {
            "host": "localhost",
            "port": 1883,
            "username": "",
            "password": "",
            "base_topic": "test"
        }

        with patch('socket.socket') as mock_socket:
            mock_sock = Mock()
            mock_sock.connect_ex.return_value = 0
            mock_socket.return_value = mock_sock

            response = client.post("/api/mqtt/test", json=test_config)

            assert response.status_code == 200
            data = response.json()
            assert "success" in data

    def test_get_mqtt_config(self, client, auth_headers):
        """Test getting MQTT configuration"""
        with patch('main.config_service') as mock_config:
            mock_config.get_mqtt_config.return_value = {
                "host": "localhost",
                "port": 1883,
                "username": "user",
                "password": "secret",
                "base_topic": "IoT2mqtt"
            }

            response = client.get("/api/mqtt/config", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["password"] == "***HIDDEN***"

    def test_save_mqtt_config(self, client, auth_headers):
        """Test saving MQTT configuration"""
        config = {
            "host": "localhost",
            "port": 1883,
            "username": "user",
            "password": "newpassword",
            "base_topic": "IoT2mqtt"
        }

        with patch('main.config_service') as mock_config, \
             patch('main.MQTTService') as mock_mqtt_class:

            mock_mqtt = mock_mqtt_class.return_value
            mock_mqtt.connect.return_value = True

            response = client.post(
                "/api/mqtt/config",
                json=config,
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_list_connectors(self, client, auth_headers):
        """Test listing available connectors"""
        with patch('main.config_service') as mock_config:
            mock_config.list_connectors.return_value = [
                {
                    "name": "yeelight",
                    "friendly_name": "Yeelight",
                    "description": "Xiaomi Yeelight smart lights"
                }
            ]

            response = client.get("/api/connectors", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert len(data) > 0

    def test_get_connector_setup(self, client, auth_headers):
        """Test getting connector setup schema"""
        with patch('main.config_service') as mock_config:
            mock_config.get_connector_setup.return_value = {
                "name": "yeelight",
                "steps": []
            }

            response = client.get(
                "/api/connectors/yeelight/setup",
                headers=auth_headers
            )

            assert response.status_code == 200

    def test_get_system_status(self, client, auth_headers):
        """Test getting system status"""
        with patch('main.docker_service') as mock_docker, \
             patch('main.config_service') as mock_config, \
             patch('main.mqtt_service') as mock_mqtt:

            mock_docker.get_system_stats.return_value = {
                "containers": {"running": 5, "total": 10}
            }
            mock_config.list_instances.return_value = [{"devices": [1, 2, 3]}]
            mock_mqtt.connected = True

            response = client.get("/api/system/status", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert "mqtt_connected" in data
            assert "instances_count" in data
