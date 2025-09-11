#!/usr/bin/env python3
"""
Tests for Discovery API endpoints
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Import the router
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from api.discovery import router, DiscoveredDevice, AddDeviceRequest, ManualDeviceRequest

# Create test app
app = FastAPI()
app.include_router(router)

client = TestClient(app)


class TestDiscoveryAPI:
    """Test Discovery API endpoints"""
    
    @pytest.fixture
    def mock_discovered_file(self):
        """Create a temporary discovered devices file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            data = {
                "last_scan": datetime.now().isoformat(),
                "devices": [
                    {
                        "id": "yeelight_192_168_1_100",
                        "name": "Test Light",
                        "integration": "yeelight",
                        "ip": "192.168.1.100",
                        "port": 55443,
                        "model": "color",
                        "discovered_at": datetime.now().isoformat(),
                        "added": False
                    },
                    {
                        "id": "yeelight_192_168_1_101",
                        "name": "Added Light",
                        "integration": "yeelight",
                        "ip": "192.168.1.101",
                        "discovered_at": datetime.now().isoformat(),
                        "added": True
                    }
                ]
            }
            json.dump(data, f)
            return Path(f.name)
    
    def test_get_discovered_devices(self, mock_discovered_file):
        """Test getting discovered devices"""
        with patch('api.discovery.Path') as mock_path:
            mock_path.return_value = mock_discovered_file
            mock_path.return_value.exists.return_value = True
            
            response = client.get("/api/discovery/devices")
            
            assert response.status_code == 200
            devices = response.json()
            assert len(devices) == 2
            assert devices[0]["id"] == "yeelight_192_168_1_100"
            assert devices[0]["added"] is False
    
    def test_get_discovered_devices_empty(self):
        """Test getting devices when file doesn't exist"""
        with patch('api.discovery.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            
            response = client.get("/api/discovery/devices")
            
            assert response.status_code == 200
            assert response.json() == []
    
    def test_add_discovered_device(self, mock_discovered_file):
        """Test adding a discovered device"""
        with patch('api.discovery.Path') as mock_path:
            mock_path.return_value = mock_discovered_file
            mock_path.return_value.exists.return_value = True
            
            # Mock config service
            with patch('api.discovery.config_service') as mock_config:
                mock_config.connectors_path = Path("/test/connectors")
                
                # Mock docker service
                with patch('api.discovery.docker_service') as mock_docker:
                    mock_docker.create_or_update_container = Mock()
                    
                    request_data = {
                        "device_id": "yeelight_192_168_1_100",
                        "instance_id": "living_room",
                        "friendly_name": "Living Room Light"
                    }
                    
                    response = client.post(
                        "/api/discovery/devices/yeelight_192_168_1_100/add",
                        json=request_data
                    )
                    
                    assert response.status_code == 200
                    result = response.json()
                    assert result["status"] == "success"
                    assert result["instance_id"] == "living_room"
                    
                    # Verify Docker was called
                    mock_docker.create_or_update_container.assert_called_once()
    
    def test_add_device_not_found(self, mock_discovered_file):
        """Test adding a device that doesn't exist"""
        with patch('api.discovery.Path') as mock_path:
            mock_path.return_value = mock_discovered_file
            mock_path.return_value.exists.return_value = True
            
            request_data = {
                "device_id": "nonexistent",
                "instance_id": "test",
                "friendly_name": "Test"
            }
            
            response = client.post(
                "/api/discovery/devices/nonexistent/add",
                json=request_data
            )
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"]
    
    def test_add_device_manually(self):
        """Test manually adding a device"""
        with patch('api.discovery.config_service') as mock_config:
            mock_config.connectors_path = Path("/test/connectors")
            
            # Mock manifest file
            manifest = {
                "manual_config": {
                    "fields": [
                        {"name": "port", "default": 55443}
                    ],
                    "test_connection": {
                        "enabled": False
                    }
                }
            }
            
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(manifest)
                
                with patch('api.discovery.Path') as mock_path:
                    mock_path.return_value.exists.return_value = True
                    
                    with patch('api.discovery.docker_service') as mock_docker:
                        mock_docker.create_or_update_container = Mock()
                        
                        request_data = {
                            "integration": "yeelight",
                            "instance_id": "manual_device",
                            "friendly_name": "Manual Device",
                            "ip": "192.168.1.200",
                            "port": 55443,
                            "name": "Test Device"
                        }
                        
                        response = client.post("/api/discovery/manual", json=request_data)
                        
                        assert response.status_code == 200
                        result = response.json()
                        assert result["status"] == "success"
                        assert result["instance_id"] == "manual_device"
    
    def test_scan_single_integration(self):
        """Test triggering a scan for single integration"""
        manifest = {
            "discovery": {
                "supported": True,
                "timeout": 10
            }
        }
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(manifest)
            
            with patch('api.discovery.Path') as mock_path:
                mock_path.return_value.exists.return_value = True
                
                with patch('api.discovery.BackgroundTasks') as mock_bg:
                    mock_bg_instance = Mock()
                    mock_bg.return_value = mock_bg_instance
                    
                    response = client.post("/api/discovery/scan/yeelight")
                    
                    assert response.status_code == 200
                    result = response.json()
                    assert result["status"] == "started"
                    assert "yeelight" in result["message"]
    
    def test_scan_unsupported_integration(self):
        """Test scanning integration that doesn't support discovery"""
        manifest = {
            "discovery": {
                "supported": False
            }
        }
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(manifest)
            
            with patch('api.discovery.Path') as mock_path:
                mock_path.return_value.exists.return_value = True
                
                response = client.post("/api/discovery/scan/test")
                
                assert response.status_code == 400
                assert "not supported" in response.json()["detail"]
    
    def test_get_discovery_status(self, mock_discovered_file):
        """Test getting discovery status"""
        with patch('api.discovery.Path') as mock_path:
            mock_path.return_value = mock_discovered_file
            mock_path.return_value.exists.return_value = True
            
            response = client.get("/api/discovery/status")
            
            assert response.status_code == 200
            status = response.json()
            assert status["status"] == "idle"
            assert status["total_devices"] == 2
            assert status["added_devices"] == 1
            assert status["available_devices"] == 1
            assert status["last_scan"] is not None
    
    def test_remove_discovered_device(self, mock_discovered_file):
        """Test removing a discovered device"""
        with patch('api.discovery.Path') as mock_path:
            mock_path.return_value = mock_discovered_file
            mock_path.return_value.exists.return_value = True
            
            # Read initial data
            with open(mock_discovered_file, 'r') as f:
                initial_data = json.load(f)
            initial_count = len(initial_data["devices"])
            
            response = client.delete("/api/discovery/devices/yeelight_192_168_1_100")
            
            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "success"
            
            # Verify device was removed from file
            with open(mock_discovered_file, 'r') as f:
                updated_data = json.load(f)
            assert len(updated_data["devices"]) == initial_count - 1
    
    def test_remove_nonexistent_device(self, mock_discovered_file):
        """Test removing a device that doesn't exist"""
        with patch('api.discovery.Path') as mock_path:
            mock_path.return_value = mock_discovered_file
            mock_path.return_value.exists.return_value = True
            
            response = client.delete("/api/discovery/devices/nonexistent")
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test WebSocket connection for discovery updates"""
        from fastapi.testclient import TestClient
        
        with TestClient(app) as client:
            with patch('api.discovery.Path') as mock_path:
                mock_path.return_value.exists.return_value = True
                mock_path.return_value.stat.return_value.st_mtime = 123456
                
                with patch('builtins.open', create=True) as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
                        "devices": []
                    })
                    
                    with client.websocket_connect("/api/discovery/ws") as websocket:
                        # Should receive initial data
                        data = websocket.receive_json()
                        assert "devices" in data
    
    @pytest.mark.asyncio
    async def test_run_discovery_for_integration(self):
        """Test running discovery for an integration"""
        from api.discovery import run_discovery_for_integration
        
        manifest = {
            "discovery": {
                "supported": True,
                "timeout": 1,
                "network_mode": "host",
                "command": "python discovery.py"
            }
        }
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(manifest)
            
            with patch('api.discovery.Path') as mock_path:
                mock_path.return_value.exists.return_value = True
                
                with patch('api.discovery.docker') as mock_docker:
                    # Mock container
                    mock_container = MagicMock()
                    mock_container.status = "exited"
                    mock_container.logs.return_value = b'[{"id": "test", "name": "Test Device"}]'
                    
                    mock_docker.from_env.return_value.containers.run.return_value = mock_container
                    
                    # Run discovery
                    await run_discovery_for_integration("test_integration")
                    
                    # Verify Docker was called
                    mock_docker.from_env.return_value.containers.run.assert_called_once()
                    mock_container.remove.assert_called_once_with(force=True)


class TestDiscoveryModels:
    """Test Pydantic models"""
    
    def test_discovered_device_model(self):
        """Test DiscoveredDevice model"""
        device_data = {
            "id": "test_device",
            "name": "Test Device",
            "integration": "test",
            "ip": "192.168.1.1",
            "port": 8080,
            "model": "test_model",
            "manufacturer": "Test Corp",
            "capabilities": {"power": True},
            "discovered_at": datetime.now().isoformat(),
            "added": False
        }
        
        device = DiscoveredDevice(**device_data)
        assert device.id == "test_device"
        assert device.ip == "192.168.1.1"
        assert device.capabilities["power"] is True
    
    def test_add_device_request_validation(self):
        """Test AddDeviceRequest validation"""
        # Valid instance_id
        request = AddDeviceRequest(
            device_id="test",
            instance_id="valid_instance",
            friendly_name="Test"
        )
        assert request.instance_id == "valid_instance"
        
        # Invalid instance_id should raise error
        with pytest.raises(ValueError):
            AddDeviceRequest(
                device_id="test",
                instance_id="Invalid Instance!",  # Contains space and uppercase
                friendly_name="Test"
            )
    
    def test_manual_device_request(self):
        """Test ManualDeviceRequest model"""
        request = ManualDeviceRequest(
            integration="yeelight",
            instance_id="manual_device",
            friendly_name="Manual",
            ip="192.168.1.100",
            port=55443,
            name="Test Device",
            model="color",
            config={"extra": "config"}
        )
        
        assert request.integration == "yeelight"
        assert request.port == 55443
        assert request.config["extra"] == "config"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])