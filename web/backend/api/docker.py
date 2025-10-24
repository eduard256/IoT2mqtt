"""
Docker management API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
from jose import JWTError, jwt
import os
import logging

# Import from parent directory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.schemas import ContainerInfo, ContainerLogs
from services.docker_service import DockerService
from services.jwt_config import get_jwt_secret, ALGORITHM

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Docker"])

# JWT Configuration
SECRET_KEY = get_jwt_secret()

# Services
docker_service = DockerService()
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/containers", response_model=List[ContainerInfo])
async def list_containers(all: bool = True, token_data=Depends(verify_token)):
    """List Docker containers"""
    containers = docker_service.list_containers(all=all)
    return [ContainerInfo(**c) for c in containers]


@router.post("/containers/{container_id}/start")
async def start_container(container_id: str, token_data=Depends(verify_token)):
    """Start container"""
    if docker_service.start_container(container_id):
        return {"success": True, "message": "Container started"}
    else:
        return {"success": False, "message": "Failed to start container"}


@router.post("/containers/{container_id}/stop")
async def stop_container(container_id: str, token_data=Depends(verify_token)):
    """Stop container"""
    if docker_service.stop_container(container_id):
        return {"success": True, "message": "Container stopped"}
    else:
        return {"success": False, "message": "Failed to stop container"}


@router.post("/containers/{container_id}/restart")
async def restart_container(container_id: str, token_data=Depends(verify_token)):
    """Restart container"""
    if docker_service.restart_container(container_id):
        return {"success": True, "message": "Container restarted"}
    else:
        return {"success": False, "message": "Failed to restart container"}


@router.delete("/containers/{container_id}")
async def delete_container(container_id: str, force: bool = False, token_data=Depends(verify_token)):
    """Delete container"""
    # Stop container first if running
    docker_service.stop_container(container_id)
    
    # Remove container
    if docker_service.remove_container(container_id, force=force):
        return {"success": True, "message": "Container deleted"}
    else:
        return {"success": False, "message": "Failed to delete container"}


@router.get("/containers/{container_id}/logs")
async def get_container_logs(
    container_id: str, 
    lines: int = 100,
    token_data=Depends(verify_token)
):
    """Get container logs"""
    logs = list(docker_service.get_container_logs(container_id, lines=lines))
    return ContainerLogs(container_id=container_id, logs=logs)
