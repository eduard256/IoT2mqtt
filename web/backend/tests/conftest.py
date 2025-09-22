from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch):
    """Setup isolated test environment"""
    # Create test secrets directory
    test_secrets = tmp_path / "secrets"
    test_secrets.mkdir(parents=True, exist_ok=True)

    # Create master key
    master_key_path = test_secrets / ".master.key"
    master_key_path.write_bytes(Fernet.generate_key())

    # Set environment variables
    monkeypatch.setenv("IOT2MQTT_SECRETS_PATH", str(test_secrets))
    monkeypatch.setenv("IOT2MQTT_PATH", str(tmp_path))

    # Create required directories
    (tmp_path / "connectors").mkdir(exist_ok=True)
    (tmp_path / "instances").mkdir(exist_ok=True)

    return tmp_path


@pytest.fixture
def mock_docker_client():
    """Mock Docker client for testing"""
    mock_client = Mock()
    mock_container = Mock()
    mock_container.short_id = "abc123"
    mock_container.status = "running"
    mock_container.name = "test_container"
    mock_container.attrs = {"State": {"Status": "running"}, "Created": "2024-01-01T00:00:00Z"}
    mock_container.ports = {}
    mock_container.labels = {}

    mock_client.containers.list.return_value = [mock_container]
    mock_client.containers.get.return_value = mock_container
    mock_client.images.build.return_value = (Mock(), [])
    mock_client.containers.run.return_value = mock_container

    return mock_client


@pytest.fixture
def mock_mqtt_client():
    """Mock MQTT client for testing"""
    mock_client = Mock()
    mock_client.connect.return_value = 0
    mock_client.publish.return_value.rc = 0
    mock_client.loop_start.return_value = None
    mock_client.loop_stop.return_value = None
    mock_client.disconnect.return_value = None

    return mock_client
