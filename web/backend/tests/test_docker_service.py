"""
Tests for Docker service
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import docker

from services.docker_service import DockerService


class TestDockerService:
    """Test Docker service functionality"""

    @pytest.fixture
    def mock_docker_client(self):
        """Mock Docker client"""
        mock_client = Mock()

        # Mock container
        mock_container = Mock()
        mock_container.short_id = "abc123"
        mock_container.name = "iot2mqtt_test_instance"
        mock_container.status = "running"
        mock_container.attrs = {
            "State": {"Status": "running"},
            "Created": "2024-01-01T00:00:00Z"
        }
        mock_container.ports = {}
        mock_container.labels = {
            "iot2mqtt.type": "connector",
            "iot2mqtt.connector": "test",
            "iot2mqtt.instance": "instance"
        }
        mock_container.image.tags = ["iot2mqtt_test:latest"]

        mock_client.containers.list.return_value = [mock_container]
        mock_client.containers.get.return_value = mock_container
        mock_client.containers.run.return_value = mock_container
        mock_client.images.build.return_value = (Mock(), [])
        mock_client.images.get.return_value = Mock()
        mock_client.ping.return_value = True

        return mock_client

    @pytest.fixture
    def docker_service(self, setup_test_env, mock_docker_client):
        """Create DockerService with mocked client"""
        with patch('services.docker_service.docker.DockerClient') as mock_docker:
            mock_docker.return_value = mock_docker_client
            service = DockerService(base_path=str(setup_test_env))
            service.client = mock_docker_client
            return service

    def test_init_with_docker_connection(self, setup_test_env):
        """Test DockerService initialization with successful Docker connection"""
        with patch('services.docker_service.docker.DockerClient') as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            service = DockerService(base_path=str(setup_test_env))

            assert service.client == mock_client
            assert service.base_path == setup_test_env

    def test_init_without_docker_connection(self, setup_test_env):
        """Test DockerService initialization when Docker is not available"""
        with patch('services.docker_service.docker.DockerClient') as mock_docker:
            mock_docker.side_effect = Exception("Docker not available")

            service = DockerService(base_path=str(setup_test_env))

            assert service.client is None

    def test_list_containers(self, docker_service, mock_docker_client):
        """Test listing containers"""
        containers = docker_service.list_containers()

        assert len(containers) == 1
        container = containers[0]
        assert container["id"] == "abc123"
        assert container["name"] == "iot2mqtt_test_instance"
        assert container["status"] == "running"
        assert container["connector_type"] == "test"
        assert container["instance_id"] == "instance"

    def test_list_containers_filters_web_container(self, docker_service, mock_docker_client):
        """Test that web container is filtered out from list"""
        web_container = Mock()
        web_container.name = "iot2mqtt_web"

        mock_docker_client.containers.list.return_value = [web_container]

        containers = docker_service.list_containers()
        assert len(containers) == 0

    def test_get_container_exists(self, docker_service, mock_docker_client):
        """Test getting existing container"""
        container = docker_service.get_container("test_container")

        assert container is not None
        mock_docker_client.containers.get.assert_called_once_with("test_container")

    def test_get_container_not_found(self, docker_service, mock_docker_client):
        """Test getting non-existent container"""
        mock_docker_client.containers.get.side_effect = docker.errors.NotFound("Container not found")

        container = docker_service.get_container("nonexistent")

        assert container is None

    def test_get_container_info(self, docker_service, mock_docker_client):
        """Test getting container info"""
        mock_container = mock_docker_client.containers.get.return_value
        mock_container.reload.return_value = None

        info = docker_service.get_container_info("test_container")

        assert info is not None
        assert info["id"] == "abc123"
        assert info["name"] == "iot2mqtt_test_instance"
        assert info["status"] == "running"

    def test_start_container(self, docker_service, mock_docker_client):
        """Test starting container"""
        mock_container = mock_docker_client.containers.get.return_value
        mock_container.start.return_value = None

        result = docker_service.start_container("test_container")

        assert result is True
        mock_container.start.assert_called_once()

    def test_stop_container(self, docker_service, mock_docker_client):
        """Test stopping container"""
        mock_container = mock_docker_client.containers.get.return_value
        mock_container.stop.return_value = None

        result = docker_service.stop_container("test_container")

        assert result is True
        mock_container.stop.assert_called_once_with(timeout=10)

    def test_restart_container(self, docker_service, mock_docker_client):
        """Test restarting container"""
        mock_container = mock_docker_client.containers.get.return_value
        mock_container.restart.return_value = None

        result = docker_service.restart_container("test_container")

        assert result is True
        mock_container.restart.assert_called_once_with(timeout=10)

    def test_remove_container(self, docker_service, mock_docker_client):
        """Test removing container"""
        mock_container = mock_docker_client.containers.get.return_value
        mock_container.remove.return_value = None

        result = docker_service.remove_container("test_container")

        assert result is True
        mock_container.remove.assert_called_once_with(force=False)

    def test_build_image_success(self, docker_service, mock_docker_client, setup_test_env):
        """Test successful image building"""
        # Create connector directory
        connector_path = setup_test_env / "connectors" / "test_connector"
        connector_path.mkdir(parents=True)

        # Create Dockerfile
        dockerfile = connector_path / "Dockerfile"
        dockerfile.write_text("FROM python:3.11\nWORKDIR /app")

        mock_image = Mock()
        mock_docker_client.images.build.return_value = (mock_image, [{"stream": "Building..."}])

        result = docker_service.build_image("test_connector")

        assert result is True
        mock_docker_client.images.build.assert_called_once()

    def test_build_image_creates_default_dockerfile(self, docker_service, mock_docker_client, setup_test_env):
        """Test that default Dockerfile is created when missing"""
        connector_path = setup_test_env / "connectors" / "test_connector"
        connector_path.mkdir(parents=True)

        mock_image = Mock()
        mock_docker_client.images.build.return_value = (mock_image, [])

        result = docker_service.build_image("test_connector")

        assert result is True
        assert (connector_path / "Dockerfile").exists()

    def test_create_container_success(self, docker_service, mock_docker_client, setup_test_env):
        """Test successful container creation"""
        config = {"test_config": "value"}

        # Mock image exists
        mock_docker_client.images.get.return_value = Mock()

        result = docker_service.create_container("test_connector", "test_instance", config)

        assert result == "abc123"
        mock_docker_client.containers.run.assert_called_once()

    def test_create_container_builds_missing_image(self, docker_service, mock_docker_client, setup_test_env):
        """Test container creation when image doesn't exist"""
        config = {"test_config": "value"}

        # Mock image doesn't exist, then exists after build
        mock_docker_client.images.get.side_effect = [
            docker.errors.ImageNotFound("Image not found"),
            Mock()  # After build
        ]

        # Mock build_image
        with patch.object(docker_service, 'build_image', return_value=True):
            result = docker_service.create_container("test_connector", "test_instance", config)

        assert result == "abc123"

    def test_get_container_logs(self, docker_service, mock_docker_client):
        """Test getting container logs"""
        mock_container = mock_docker_client.containers.get.return_value
        mock_container.logs.return_value = [
            b"2024-01-01T00:00:00Z INFO: Starting application",
            b"2024-01-01T00:00:01Z ERROR: Connection failed"
        ]

        logs = list(docker_service.get_container_logs("test_container", lines=10))

        assert len(logs) == 2
        assert logs[0]["level"] == "info"
        assert logs[1]["level"] == "error"
        assert "Starting application" in logs[0]["content"]

    def test_get_system_stats(self, docker_service, mock_docker_client):
        """Test getting system statistics"""
        # Mock containers list
        running_container = Mock()
        running_container.attrs = {"State": {"Status": "running"}}
        stopped_container = Mock()
        stopped_container.attrs = {"State": {"Status": "exited"}}

        docker_service.list_containers = Mock(return_value=[
            {"state": "running"},
            {"state": "exited"}
        ])

        # Mock images
        mock_image = Mock()
        mock_image.tags = ["iot2mqtt_test:latest"]
        mock_docker_client.images.list.return_value = [mock_image]

        stats = docker_service.get_system_stats()

        assert stats["containers"]["total"] == 2
        assert stats["containers"]["running"] == 1
        assert stats["containers"]["stopped"] == 1
        assert stats["images"] == 1

    def test_docker_client_error_handling(self, docker_service, mock_docker_client):
        """Test error handling when Docker operations fail"""
        mock_docker_client.containers.get.side_effect = Exception("Docker error")

        result = docker_service.start_container("test_container")
        assert result is False

        result = docker_service.stop_container("test_container")
        assert result is False

        result = docker_service.restart_container("test_container")
        assert result is False