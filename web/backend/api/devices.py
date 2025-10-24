"""
Devices API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from typing import Dict, Any
import json
import os
import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.config_service import ConfigService
from services.docker_service import DockerService
from services.jwt_config import get_jwt_secret, ALGORITHM

router = APIRouter(prefix="/api/devices", tags=["Devices"])

config_service = ConfigService()
docker_service = DockerService()
logger = logging.getLogger(__name__)
security = HTTPBearer()

# JWT Configuration
SECRET_KEY = get_jwt_secret()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def _collect_all_devices():
    """Get all devices from all instances"""
    try:
        devices = []

        all_instances = config_service.list_instances()
        if not all_instances:
            return {
                "success": True,
                "message": "No connectors found",
                "devices": []
            }

        for instance in all_instances:
            connector_type = instance.get("connector_type")
            instance_id = instance.get("instance_id")

            if not connector_type or not instance_id:
                continue

            instance_devices = instance.get("devices", [])

            container_name = f"{docker_service.prefix}{connector_type}_{instance_id}"
            container_info = docker_service.get_container_info(container_name) if docker_service.client else None
            instance_online = container_info and container_info.get("status") in {"running", "healthy"}

            for device in instance_devices:
                try:
                    device_id = device.get("device_id") or device.get("id") or f"{connector_type}_{instance_id}"
                    friendly_name = device.get("friendly_name") or device.get("name") or device_id
                    devices.append({
                        "instance_id": instance_id,
                        "connector_type": connector_type,
                        "device_id": device_id,
                        "friendly_name": friendly_name,
                        "device_type": device.get("device_type") or connector_type,
                        "device_class": device.get("device_class"),
                        "state": device.get("state", {}),
                        "capabilities": device.get("capabilities", {}),
                        "online": bool(instance_online and device.get("enabled", True)),
                        "enabled": device.get("enabled", True),
                        "room": device.get("room"),
                        "model": device.get("model"),
                        "manufacturer": device.get("manufacturer"),
                        "last_update": device.get("last_update")
                    })
                except Exception as err:
                    logger.error("Failed to serialize device from %s/%s: %s", connector_type, instance_id, err)

        return {
            "success": True,
            "message": f"Found {len(devices)} devices",
            "devices": devices
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get devices: {str(e)}"
        )


@router.get("")
@router.get("/")
async def get_all_devices(token_data=Depends(verify_token)):
    return await _collect_all_devices()
