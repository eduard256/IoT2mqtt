"""
Discovery API endpoints
Управление обнаружением устройств
"""

import json
import asyncio
import docker
import logging
import requests
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from pydantic import BaseModel, Field

from services.config_service import ConfigService
from services.docker_service import DockerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discovery", tags=["Discovery"])

# Services
config_service = ConfigService()
docker_service = DockerService()


class DiscoveredDevice(BaseModel):
    """Discovered device model"""
    id: str
    name: str
    integration: str
    ip: Optional[str] = None
    port: Optional[int] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None
    discovered_at: str
    added: bool = False


class AddDeviceRequest(BaseModel):
    """Request to add discovered device"""
    device_id: str
    instance_id: str = Field(..., pattern="^[a-z0-9_-]+$")
    friendly_name: str
    config: Optional[Dict[str, Any]] = {}


class ManualDeviceRequest(BaseModel):
    """Request to add device manually"""
    integration: str
    instance_id: str = Field(..., pattern="^[a-z0-9_-]+$")
    friendly_name: str
    ip: str
    port: Optional[int] = None
    name: str
    model: Optional[str] = None
    config: Optional[Dict[str, Any]] = {}


class ScanRequest(BaseModel):
    """Request to scan for devices"""
    integration: str
    timeout: int = Field(default=30, ge=5, le=120)


@router.get("/devices", response_model=List[DiscoveredDevice])
async def get_discovered_devices():
    """Get all discovered devices"""
    try:
        discovered_path = Path("/app") / "discovered_devices.json"
        
        if not discovered_path.exists():
            return []
        
        with open(discovered_path, 'r') as f:
            data = json.load(f)
        
        devices = data.get("devices", [])
        
        # Filter out already added devices if needed
        return [DiscoveredDevice(**device) for device in devices]
        
    except Exception as e:
        logger.error(f"Failed to load discovered devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/devices/{device_id}/add")
async def add_discovered_device(device_id: str, request: AddDeviceRequest):
    """Add a discovered device to the system"""
    try:
        # Load discovered devices
        discovered_path = Path("/app") / "discovered_devices.json"
        
        if not discovered_path.exists():
            raise HTTPException(status_code=404, detail="No discovered devices found")
        
        with open(discovered_path, 'r') as f:
            data = json.load(f)
        
        # Find the device
        device = None
        for d in data.get("devices", []):
            if d["id"] == device_id:
                device = d
                break
        
        if not device:
            raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
        
        # Create instance configuration
        instance_config = {
            "instance_id": request.instance_id,
            "instance_type": "device",
            "connector_type": device["integration"],
            "friendly_name": request.friendly_name,
            "connection": {
                "ip": device.get("ip"),
                "port": device.get("port", 55443)
            },
            "devices": [{
                "device_id": device_id,
                "global_id": f"{request.instance_id}_{device_id}",
                "friendly_name": device.get("name", request.friendly_name),
                "model": device.get("model", "unknown"),
                "enabled": True,
                "capabilities": device.get("capabilities", {})
            }],
            "enabled": True,
            "update_interval": 10,
            **request.config
        }
        
        # Save instance configuration
        instance_path = config_service.connectors_path / device["integration"] / "instances"
        instance_path.mkdir(exist_ok=True)
        
        config_file = instance_path / f"{request.instance_id}.json"
        with open(config_file, 'w') as f:
            json.dump(instance_config, f, indent=2)
        
        # Mark device as added
        for d in data["devices"]:
            if d["id"] == device_id:
                d["added"] = True
                d["added_at"] = datetime.now().isoformat()
                break
        
        # Save updated discovered devices
        with open(discovered_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Start the container
        docker_service.create_or_update_container(
            device["integration"],
            request.instance_id,
            instance_config
        )
        
        return {
            "status": "success",
            "message": f"Device {device_id} added successfully",
            "instance_id": request.instance_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add device: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manual")
async def add_device_manually(request: ManualDeviceRequest):
    """Add a device manually without discovery"""
    try:
        # Load integration manifest
        manifest_path = config_service.connectors_path / request.integration / "manifest.json"
        
        if not manifest_path.exists():
            raise HTTPException(status_code=404, detail=f"Integration {request.integration} not found")
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        # Test connection using test-runner service
        test_runner_url = os.environ.get("TEST_RUNNER_URL", "http://localhost:8001")
        
        # Test TCP connection first
        try:
            response = requests.post(
                f"{test_runner_url}/test/tcp",
                json={
                    "ip": request.ip,
                    "port": request.port or manifest.get("manual_config", {}).get("fields", [{}])[1].get("default", 55443),
                    "timeout": 5
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if not result.get("success"):
                    logger.warning(f"Device connection test failed: {result.get('error', 'Unknown error')}")
                    # Don't fail, just warn - user might want to add anyway
            else:
                logger.error(f"Test runner error: {response.status_code}")
        except requests.RequestException as e:
            logger.error(f"Failed to connect to test runner: {e}")
            # Continue anyway - test runner might be down
        
        # Create device ID
        device_id = f"{request.integration}_{request.ip.replace('.', '_')}"
        
        # Create instance configuration
        instance_config = {
            "instance_id": request.instance_id,
            "instance_type": "device",
            "connector_type": request.integration,
            "friendly_name": request.friendly_name,
            "connection": {
                "ip": request.ip,
                "port": request.port or manifest.get("manual_config", {}).get("fields", [{}])[1].get("default", 55443)
            },
            "devices": [{
                "device_id": device_id,
                "global_id": f"{request.instance_id}_{device_id}",
                "friendly_name": request.name,
                "model": request.model or "unknown",
                "enabled": True,
                "ip": request.ip,
                "port": request.port
            }],
            "enabled": True,
            "update_interval": 10,
            **request.config
        }
        
        # Save instance configuration
        instance_path = config_service.connectors_path / request.integration / "instances"
        instance_path.mkdir(exist_ok=True)
        
        config_file = instance_path / f"{request.instance_id}.json"
        with open(config_file, 'w') as f:
            json.dump(instance_config, f, indent=2)
        
        # Start the container
        docker_service.create_or_update_container(
            request.integration,
            request.instance_id,
            instance_config
        )
        
        return {
            "status": "success",
            "message": f"Device added manually",
            "device_id": device_id,
            "instance_id": request.instance_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add device manually: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan/{integration}")
async def scan_single_integration(integration: str, background_tasks: BackgroundTasks):
    """Trigger discovery scan for a single integration"""
    try:
        # Check if integration exists
        manifest_path = config_service.connectors_path / integration / "manifest.json"
        
        if not manifest_path.exists():
            raise HTTPException(status_code=404, detail=f"Integration {integration} not found")
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        if not manifest.get("discovery", {}).get("supported", False):
            raise HTTPException(status_code=400, detail=f"Discovery not supported for {integration}")
        
        # Run discovery in background
        background_tasks.add_task(run_discovery_for_integration, integration)
        
        return {
            "status": "started",
            "message": f"Discovery started for {integration}",
            "check_endpoint": "/api/discovery/status"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start discovery: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def run_discovery_for_integration(integration: str):
    """Run discovery for a single integration using test-runner"""
    try:
        test_runner_url = os.environ.get("TEST_RUNNER_URL", "http://localhost:8001")
        
        # Request discovery from test-runner
        response = requests.post(
            f"{test_runner_url}/discovery/{integration}",
            timeout=5
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to start discovery: {response.text}")
            return
        
        # Poll for results
        max_polls = 30  # 30 seconds max
        for _ in range(max_polls):
            await asyncio.sleep(1)
            
            # Check status
            status_response = requests.get(
                f"{test_runner_url}/discovery/{integration}/status",
                timeout=5
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                
                if status_data.get("status") == "completed":
                    devices = status_data.get("devices", [])
                    
                    if devices:
                        # Add integration field to each device
                        for device in devices:
                            device["integration"] = integration
                            device["discovered_at"] = datetime.now().isoformat()
                            device["added"] = False
                        
                        # Save discovered devices
                        discovered_path = Path("/app") / "discovered_devices.json"
                        
                        if discovered_path.exists():
                            with open(discovered_path, 'r') as f:
                                data = json.load(f)
                        else:
                            data = {"devices": []}
                        
                        # Merge devices
                        for device in devices:
                            existing = next((d for d in data["devices"] if d["id"] == device["id"]), None)
                            if existing:
                                existing.update(device)
                            else:
                                data["devices"].append(device)
                        
                        data["last_scan"] = datetime.now().isoformat()
                        
                        # Save
                        with open(discovered_path, 'w') as f:
                            json.dump(data, f, indent=2)
                        
                        logger.info(f"Discovery completed for {integration}: found {len(devices)} devices")
                    else:
                        logger.info(f"No devices found for {integration}")
                    
                    return
        
        logger.warning(f"Discovery timeout for {integration}")
        
    except Exception as e:
        logger.error(f"Discovery failed for {integration}: {e}")


@router.get("/status")
async def get_discovery_status():
    """Get current discovery status"""
    try:
        discovered_path = Path("/app") / "discovered_devices.json"
        
        if not discovered_path.exists():
            return {
                "status": "idle",
                "last_scan": None,
                "total_devices": 0,
                "added_devices": 0,
                "available_devices": 0,
                "devices": []
            }
        
        with open(discovered_path, 'r') as f:
            data = json.load(f)
        
        devices = data.get("devices", [])
        added = sum(1 for d in devices if d.get("added", False))
        available = len(devices) - added
        
        return {
            "status": "idle",  # Could be enhanced to show if discovery is running
            "last_scan": data.get("last_scan"),
            "total_devices": len(devices),
            "added_devices": added,
            "available_devices": available,
            "devices": devices  # Return devices for polling
        }
        
    except Exception as e:
        logger.error(f"Failed to get discovery status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws")
async def discovery_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time discovery updates"""
    await websocket.accept()
    
    try:
        # Send initial state
        discovered_path = Path("/app") / "discovered_devices.json"
        
        if discovered_path.exists():
            with open(discovered_path, 'r') as f:
                data = json.load(f)
            await websocket.send_json(data)
        
        # Monitor for changes
        last_modified = discovered_path.stat().st_mtime if discovered_path.exists() else 0
        
        while True:
            await asyncio.sleep(1)
            
            if discovered_path.exists():
                current_modified = discovered_path.stat().st_mtime
                
                if current_modified > last_modified:
                    with open(discovered_path, 'r') as f:
                        data = json.load(f)
                    await websocket.send_json(data)
                    last_modified = current_modified
                    
    except WebSocketDisconnect:
        logger.info("Discovery WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()


@router.delete("/devices/{device_id}")
async def remove_discovered_device(device_id: str):
    """Remove a device from discovered list"""
    try:
        discovered_path = Path("/app") / "discovered_devices.json"
        
        if not discovered_path.exists():
            raise HTTPException(status_code=404, detail="No discovered devices")
        
        with open(discovered_path, 'r') as f:
            data = json.load(f)
        
        # Filter out the device
        original_count = len(data.get("devices", []))
        data["devices"] = [d for d in data.get("devices", []) if d["id"] != device_id]
        
        if len(data["devices"]) == original_count:
            raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
        
        # Save
        with open(discovered_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return {"status": "success", "message": f"Device {device_id} removed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove device: {e}")
        raise HTTPException(status_code=500, detail=str(e))