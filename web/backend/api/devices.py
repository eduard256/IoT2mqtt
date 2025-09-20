"""
Devices API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from typing import Dict, Any
import json
from pathlib import Path
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.config_service import ConfigService
from services.docker_service import DockerService

router = APIRouter(prefix="/api/devices", tags=["Devices"])

config_service = ConfigService()
docker_service = DockerService()
security = HTTPBearer()

# JWT Configuration (keep in sync with main)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"


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
        
        # Get all connectors
        connectors_path = Path("connectors")
        if not connectors_path.exists():
            return {
                "success": True,
                "message": "No connectors found",
                "devices": []
            }
        
        # Iterate through each connector
        for connector_dir in connectors_path.iterdir():
            if not connector_dir.is_dir() or connector_dir.name.startswith("_"):
                continue
            
            instances_dir = connector_dir / "instances"
            if not instances_dir.exists():
                continue
            
            # Read instance configs
            for instance_file in instances_dir.glob("*.json"):
                try:
                    with open(instance_file, 'r') as f:
                        instance_config = json.load(f)
                    
                    instance_id = instance_config.get("instance_id")
                    if not instance_id:
                        continue
                    
                    # Get device list from instance config
                    instance_devices = instance_config.get("devices", [])
                    
                    # Check container status for online state
                    container_name = f"iot2mqtt_{instance_id}"
                    container_info = docker_service.get_container_info(container_name)
                    instance_online = container_info and container_info.get("status") == "running"
                    
                    for device in instance_devices:
                        devices.append({
                            "instance_id": instance_id,
                            "device_id": device.get("device_id"),
                            "name": device.get("name"),
                            "model": device.get("model"),
                            "enabled": device.get("enabled", True),
                            "online": instance_online and device.get("enabled", True),
                            "connector_type": connector_dir.name
                        })
                        
                except Exception as e:
                    print(f"Error reading instance {instance_file}: {e}")
                    continue
        
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
