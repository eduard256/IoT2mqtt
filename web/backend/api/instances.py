"""
Instances API endpoints for managing connector instances
"""

import asyncio
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from pydantic import BaseModel, Field

from services.config_service import ConfigService
from services.docker_service import DockerService
# from services.mqtt_service import MQTTService  # Will be used in future
from models.schemas import InstanceConfig

logger = logging.getLogger(__name__)  

router = APIRouter(tags=["Instances"])

# Services
config_service = ConfigService()
docker_service = DockerService()

# WebSocket connections for logs
log_connections: Dict[str, List[WebSocket]] = {}


class CreateInstanceRequest(BaseModel):
    """Request to create a new instance"""
    instance_id: str = Field(..., pattern="^[a-z0-9_-]+$")
    connector_type: str
    friendly_name: str
    config: Dict[str, Any]
    devices: List[Dict[str, Any]] = []
    enabled: bool = True
    update_interval: int = 10


class UpdateInstanceRequest(BaseModel):
    """Request to update instance configuration"""
    friendly_name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    devices: Optional[List[Dict[str, Any]]] = None
    enabled: Optional[bool] = None
    update_interval: Optional[int] = None


class InstanceError(BaseModel):
    """Instance error information"""
    timestamp: datetime
    level: str
    message: str
    details: Optional[Dict[str, Any]] = None


@router.get("/api/instances", response_model=List[InstanceConfig])
async def list_instances(connector: Optional[str] = None):
    """List all instances or instances for specific connector"""
    try:
        instances = config_service.list_instances(connector)
        
        # Add runtime status from Docker
        for instance in instances:
            container_name = f"iot2mqtt_{instance['connector_type']}_{instance['instance_id']}"
            container = docker_service.get_container(container_name)
            
            if container:
                instance["container_status"] = container.status
                instance["container_id"] = container.short_id
            else:
                instance["container_status"] = "not_created"
                instance["container_id"] = None
        
        return instances
        
    except Exception as e:
        logger.error(f"Failed to list instances: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/instances/{connector}/{instance_id}", response_model=InstanceConfig)
async def get_instance(connector: str, instance_id: str):
    """Get specific instance configuration"""
    try:
        # Load instance with secrets injected
        instance = config_service.load_instance_with_secrets(connector, instance_id)
        
        if not instance:
            raise HTTPException(status_code=404, detail="Instance not found")
        
        # Add container status
        container_name = f"iot2mqtt_{connector}_{instance_id}"
        container = docker_service.get_container(container_name)
        
        if container:
            instance["container_status"] = container.status
            instance["container_id"] = container.short_id
        
        return instance
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get instance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/instances")
async def create_instance(request: CreateInstanceRequest, background_tasks: BackgroundTasks):
    """Create new instance with Docker container"""
    try:
        # Check if instance already exists
        existing = config_service.get_instance_config(
            request.connector_type, 
            request.instance_id
        )
        if existing:
            raise HTTPException(status_code=409, detail="Instance already exists")
        
        # Prepare instance configuration
        instance_config = {
            "instance_id": request.instance_id,
            "instance_type": "device",  # Can be extended later
            "connector_type": request.connector_type,
            "friendly_name": request.friendly_name,
            "connection": request.config,
            "devices": request.devices,
            "enabled": request.enabled,
            "update_interval": request.update_interval,
            "created_at": datetime.now().isoformat()
        }
        
        # Save configuration with separated secrets
        docker_secrets = config_service.save_instance_with_secrets(
            request.connector_type,
            request.instance_id,
            instance_config
        )
        
        # Update docker-compose.yml
        compose_data = config_service.load_docker_compose()
        service_name = f"{request.connector_type}_{request.instance_id}"
        
        # Add service configuration
        compose_data["services"][service_name] = {
            "build": f"./connectors/{request.connector_type}",
            "container_name": f"iot2mqtt_{service_name}",
            "restart": "unless-stopped",
            "volumes": [
                "./shared:/app/shared:ro",
                f"./connectors/{request.connector_type}/instances:/app/instances:ro",
                "./.env:/app/.env:ro"  # Mount .env file for dynamic MQTT config
            ],
            "environment": [
                f"INSTANCE_NAME={request.instance_id}",
                "MODE=production",
                "PYTHONUNBUFFERED=1",
                "LOG_LEVEL=${LOG_LEVEL:-INFO}"  # Use LOG_LEVEL from .env with default
            ],
            "networks": ["iot2mqtt"],
            "labels": {
                "iot2mqtt.type": "connector",
                "iot2mqtt.connector": request.connector_type,
                "iot2mqtt.instance": request.instance_id
            }
        }
        
        # Add Docker secrets if any
        if docker_secrets:
            if "secrets" not in compose_data:
                compose_data["secrets"] = {}
            compose_data["secrets"].update(docker_secrets["secrets"])
            compose_data["services"][service_name]["secrets"] = docker_secrets["service_secrets"]
        
        # Check if network mode host is required
        setup = config_service.get_connector_setup(request.connector_type)
        if setup and setup.get("requirements", {}).get("network") == "host":
            compose_data["services"][service_name]["network_mode"] = "host"
            # Remove networks if using host mode
            compose_data["services"][service_name].pop("networks", None)
        
        # Save docker-compose
        config_service.save_docker_compose(compose_data)
        
        # Build and start container in background
        background_tasks.add_task(
            create_and_start_container,
            request.connector_type,
            request.instance_id,
            instance_config
        )
        
        return {
            "success": True,
            "message": "Instance created, container is starting",
            "instance_id": request.instance_id,
            "websocket_logs": f"/api/logs/{request.connector_type}_{request.instance_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create instance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def create_and_start_container(connector_type: str, instance_id: str, config: dict):
    """Build and start container for instance"""
    try:
        container_id = docker_service.create_container(connector_type, instance_id, config)
        if container_id:
            logger.info(f"Successfully created container for {connector_type}/{instance_id}: {container_id}")
        else:
            logger.error(f"Failed to create container for {connector_type}/{instance_id}")
    except Exception as e:
        logger.error(f"Error creating container: {e}")


@router.put("/api/instances/{connector}/{instance_id}")
async def update_instance(connector: str, instance_id: str, request: UpdateInstanceRequest):
    """Update instance configuration and restart container"""
    try:
        # Load existing configuration
        existing = config_service.load_instance_with_secrets(connector, instance_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Instance not found")
        
        # Update fields
        if request.friendly_name is not None:
            existing["friendly_name"] = request.friendly_name
        if request.config is not None:
            existing["connection"].update(request.config)
        if request.devices is not None:
            existing["devices"] = request.devices
        if request.enabled is not None:
            existing["enabled"] = request.enabled
        if request.update_interval is not None:
            existing["update_interval"] = request.update_interval
        
        existing["updated_at"] = datetime.now().isoformat()
        
        # Save updated configuration
        config_service.save_instance_with_secrets(connector, instance_id, existing)
        
        # Restart container
        container_name = f"iot2mqtt_{connector}_{instance_id}"
        if docker_service.restart_container(container_name):
            return {
                "success": True,
                "message": "Instance updated and container restarted"
            }
        else:
            return {
                "success": True,
                "message": "Instance updated but container restart failed",
                "warning": True
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update instance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/instances/{connector}/{instance_id}")
async def delete_instance(connector: str, instance_id: str):
    """Delete instance and stop container"""
    try:
        # Stop and remove container
        container_name = f"iot2mqtt_{connector}_{instance_id}"
        container = docker_service.get_container(container_name)
        
        if container:
            docker_service.stop_container(container_name)
            docker_service.remove_container(container_name)
        
        # Delete configuration
        if not config_service.delete_instance_config(connector, instance_id):
            raise HTTPException(status_code=404, detail="Instance not found")
        
        # Delete secrets
        config_service.secrets_manager.delete_instance_secret(instance_id)
        
        # Update docker-compose.yml
        compose_data = config_service.load_docker_compose()
        service_name = f"{connector}_{instance_id}"
        
        if service_name in compose_data.get("services", {}):
            del compose_data["services"][service_name]
            config_service.save_docker_compose(compose_data)
        
        return {
            "success": True,
            "message": "Instance deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete instance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/instances/{connector}/{instance_id}/errors")
async def get_instance_errors(connector: str, instance_id: str):
    """Get recent errors for instance from MQTT error topics"""
    """Get recent errors for instance"""
    try:
        # In future, this would connect to MQTT to get errors
        # For now, return empty list
        return []
        
        # Subscribe to error topic
        error_topic = f"{mqtt_service.base_topic}/v1/errors/{instance_id}/#"
        errors = []
        
        # Get last errors from MQTT
        # This would need implementation in MQTTService to store recent messages
        # For now, return empty list
        
        return errors
        
    except Exception as e:
        logger.error(f"Failed to get instance errors: {e}")
        return []


@router.post("/api/instances/{connector}/{instance_id}/retry")
async def retry_instance(connector: str, instance_id: str, background_tasks: BackgroundTasks):
    """Retry instance with exponential backoff"""
    try:
        container_name = f"iot2mqtt_{connector}_{instance_id}"
        
        # Add retry task to background
        background_tasks.add_task(
            retry_container_with_backoff,
            container_name,
            instance_id
        )
        
        return {
            "success": True,
            "message": "Retry initiated"
        }
        
    except Exception as e:
        logger.error(f"Failed to retry instance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def retry_container_with_backoff(container_name: str, instance_id: str, max_retries: int = 3):
    """Retry container with exponential backoff"""
    retries = 0
    backoff = 1
    
    while retries < max_retries:
        try:
            # Restart container
            if docker_service.restart_container(container_name):
                logger.info(f"Successfully restarted {container_name} on retry {retries + 1}")
                
                # Wait and check health
                await asyncio.sleep(5)
                
                container = docker_service.get_container(container_name)
                if container and container.status == "running":
                    return True
            
        except Exception as e:
            logger.error(f"Retry {retries + 1} failed for {container_name}: {e}")
        
        retries += 1
        backoff *= 2
        await asyncio.sleep(backoff)
    
    logger.error(f"All retries failed for {container_name}")
    return False


@router.websocket("/api/logs/{container_id}")
async def container_logs_websocket(websocket: WebSocket, container_id: str):
    """WebSocket endpoint for streaming container logs"""
    await websocket.accept()
    
    # Add to connections
    if container_id not in log_connections:
        log_connections[container_id] = []
    log_connections[container_id].append(websocket)
    
    try:
        # Stream logs
        async for log_entry in stream_container_logs(container_id):
            # Colorize log based on level
            log_entry["color"] = get_log_color(log_entry.get("level", "info"))
            await websocket.send_json(log_entry)
            
    except WebSocketDisconnect:
        logger.info(f"Log WebSocket disconnected for {container_id}")
    finally:
        # Remove from connections
        if container_id in log_connections:
            log_connections[container_id].remove(websocket)
            if not log_connections[container_id]:
                del log_connections[container_id]


async def stream_container_logs(container_id: str):
    """Stream container logs"""
    container = docker_service.get_container(container_id)
    if not container:
        yield {"level": "error", "content": f"Container {container_id} not found"}
        return
    
    # Stream logs
    for log in docker_service.get_container_logs(container_id, follow=True):
        yield log
        await asyncio.sleep(0.1)  # Small delay to prevent flooding


def get_log_color(level: str) -> str:
    """Get color for log level"""
    colors = {
        "error": "#ef4444",     # red-500
        "warning": "#f59e0b",   # amber-500
        "success": "#10b981",   # emerald-500
        "info": "#3b82f6",      # blue-500
        "debug": "#6b7280"      # gray-500
    }
    return colors.get(level.lower(), "#ffffff")