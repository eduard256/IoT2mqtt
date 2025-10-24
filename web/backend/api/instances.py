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
from services.port_manager import PortManager
# from services.mqtt_service import MQTTService  # Will be used in future
from models.schemas import InstanceConfig

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Instances"])

# Services
config_service = ConfigService()
docker_service = DockerService()
port_manager = PortManager(config_service.instances_path)

# WebSocket connections for logs
log_connections: Dict[str, List[WebSocket]] = {}

# Default healthcheck values
HEALTHCHECK_DEFAULTS = {
    "interval": 30,
    "timeout": 10,
    "retries": 3,
    "start_period": 10
}


def build_healthcheck_config(setup: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Build docker-compose healthcheck configuration from setup.json

    Args:
        setup: Connector setup.json content

    Returns:
        Docker-compose healthcheck dict or None if no healthcheck defined
    """
    if not setup or "healthcheck" not in setup:
        return None

    healthcheck = setup["healthcheck"]

    # Apply defaults for missing values
    healthcheck_config = {
        "interval": healthcheck.get("interval", HEALTHCHECK_DEFAULTS["interval"]),
        "timeout": healthcheck.get("timeout", HEALTHCHECK_DEFAULTS["timeout"]),
        "retries": healthcheck.get("retries", HEALTHCHECK_DEFAULTS["retries"]),
        "start_period": healthcheck.get("start_period", HEALTHCHECK_DEFAULTS["start_period"])
    }

    # Build test command - always use universal healthcheck.py script
    healthcheck_config["test"] = ["CMD", "python3", "/app/shared/healthcheck.py"]

    # Convert numeric values to strings with time units for docker-compose
    healthcheck_config["interval"] = f"{healthcheck_config['interval']}s"
    healthcheck_config["timeout"] = f"{healthcheck_config['timeout']}s"
    healthcheck_config["start_period"] = f"{healthcheck_config['start_period']}s"

    return healthcheck_config


class CreateInstanceRequest(BaseModel):
    """Request to create a new instance"""
    instance_id: Optional[str] = None  # Optional: will be auto-generated if not provided
    connector_type: str
    friendly_name: str
    config: Dict[str, Any]
    devices: List[Dict[str, Any]] = []
    enabled: bool = True
    update_interval: int = 10
    secrets: Optional[Dict[str, Any]] = None


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
        # Auto-generate instance_id if not provided or if it's "auto"
        instance_id = request.instance_id
        if not instance_id or instance_id.strip() == "" or instance_id.strip().lower() == "auto":
            instance_id = config_service.generate_unique_instance_id(request.connector_type)
            logger.info(f"Auto-generated instance_id: {instance_id}")
        else:
            # Validate and check if instance already exists
            instance_id = instance_id.strip()
            existing = config_service.get_instance_config(request.connector_type, instance_id)
            if existing:
                raise HTTPException(status_code=409, detail="Instance already exists")

        # Prepare instance configuration
        instance_config = {
            "instance_id": instance_id,
            "instance_type": "device",  # Can be extended later
            "connector_type": request.connector_type,
            "friendly_name": request.friendly_name,
            "connection": request.config,
            "devices": request.devices,
            "enabled": request.enabled,
            "update_interval": request.update_interval,
            "created_at": datetime.now().isoformat()
        }

        # Generate ports if connector requires them
        setup = config_service.get_connector_setup(request.connector_type)
        if setup and "ports" in setup and isinstance(setup["ports"], list):
            try:
                port_names = setup["ports"]
                generated_ports = port_manager.generate_ports_for_connector(port_names)
                instance_config["ports"] = generated_ports
                logger.info(f"Generated ports for {instance_id}: {generated_ports}")
            except Exception as e:
                logger.error(f"Failed to generate ports for {instance_id}: {e}")
                raise HTTPException(status_code=500, detail=f"Port generation failed: {str(e)}")

        # Maintain backwards compatibility: expose connection keys at top-level
        if isinstance(request.config, dict):
            for key, value in request.config.items():
                if key not in instance_config:
                    instance_config[key] = value

        # Auto-detect and configure parasitic connector
        # If devices have mqtt_path, this is a parasitic connector
        if request.devices and any('mqtt_path' in d for d in request.devices):
            parasite_targets = []
            for device in request.devices:
                if 'mqtt_path' in device and 'device_id' in device:
                    # Build parasite target from device
                    target = {
                        'mqtt_path': device['mqtt_path'],
                        'device_id': device['device_id'],
                        'instance_id': device.get('instance_id'),
                    }
                    # Include any extracted_data if present
                    if 'extracted_data' in device:
                        target['extracted_data'] = device['extracted_data']
                    # Include other device fields as extracted_data fallback
                    elif any(k in device for k in ['ip', 'name', 'brand', 'model']):
                        target['extracted_data'] = {
                            k: v for k, v in device.items()
                            if k not in ['mqtt_path', 'device_id', 'instance_id', 'enabled']
                        }

                    parasite_targets.append(target)

            # Add to config
            if parasite_targets:
                if 'config' not in instance_config or instance_config['config'] is None:
                    instance_config['config'] = {}
                instance_config['config']['parasite_targets'] = parasite_targets
                logger.info(f"Auto-configured parasitic connector with {len(parasite_targets)} target(s)")

        # Validate parasitic configuration if present
        parasite_targets = None
        if instance_config.get('config') and 'parasite_targets' in instance_config['config']:
            parasite_targets = instance_config['config']['parasite_targets']
        elif 'parasite_targets' in request.config:
            parasite_targets = request.config['parasite_targets']

        if parasite_targets:
            logger.info(f"Validating parasitic configuration with {len(parasite_targets)} target(s)")

            # Validate structure
            for idx, target in enumerate(parasite_targets):
                if not isinstance(target, dict):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Parasite target {idx} must be a dictionary"
                    )

                if 'mqtt_path' not in target or 'device_id' not in target:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Parasite target {idx} missing required fields (mqtt_path, device_id)"
                    )

                # Verify device_id matches configured devices
                device_ids = [d['device_id'] for d in request.devices]
                if target['device_id'] not in device_ids:
                    logger.warning(
                        f"Parasite target device_id '{target['device_id']}' not found in connector devices. "
                        f"Expected one of: {device_ids}. Device ID inheritance required for proper field association."
                    )

            # Optional: Verify parent devices exist (non-blocking)
            from api import mqtt_discovery
            mqtt_svc = mqtt_discovery.mqtt_service
            if mqtt_svc and mqtt_svc.connected:
                for target in parasite_targets:
                    mqtt_path = target.get('mqtt_path')
                    if mqtt_path:
                        state_topic = f"{mqtt_path}/state"
                        if state_topic not in mqtt_svc.topic_cache:
                            logger.warning(
                                f"Parasite target not found in MQTT cache: {mqtt_path}. "
                                f"Parent device may be offline or will come online later."
                            )

        # Save configuration with separated secrets
        docker_secrets = config_service.save_instance_with_secrets(
            request.connector_type,
            instance_id,
            instance_config,
            request.secrets
        )

        # Update docker-compose.yml
        compose_data = config_service.load_docker_compose()
        service_name = f"{request.connector_type}_{instance_id}"
        
        # Add service configuration
        compose_data.setdefault("services", {})
        compose_data.setdefault("networks", {"iot2mqtt": {"driver": "bridge"}})

        compose_data["services"][service_name] = {
            "build": f"./connectors/{request.connector_type}",
            "container_name": f"iot2mqtt_{service_name}",
            "restart": "unless-stopped",
            "volumes": [
                "./shared:/app/shared:ro",
                f"./instances/{request.connector_type}:/app/instances:ro",
                "./.env:/app/.env:ro"  # Mount .env file for dynamic MQTT config
            ],
            "environment": [
                f"INSTANCE_NAME={instance_id}",
                "MODE=production",
                "PYTHONUNBUFFERED=1",
                "LOG_LEVEL=${LOG_LEVEL:-INFO}"  # Use LOG_LEVEL from .env with default
            ],
            "networks": ["iot2mqtt"],
            "labels": {
                "iot2mqtt.type": "connector",
                "iot2mqtt.connector": request.connector_type,
                "iot2mqtt.instance": instance_id
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

        # Add healthcheck configuration from setup.json
        if setup:
            healthcheck_config = build_healthcheck_config(setup)
            if healthcheck_config:
                compose_data["services"][service_name]["healthcheck"] = healthcheck_config
                logger.info(f"Added healthcheck configuration for {service_name}")

        # Save docker-compose
        config_service.save_docker_compose(compose_data)
        
        # Build and start container in background
        background_tasks.add_task(
            create_and_start_container,
            request.connector_type,
            instance_id,
            instance_config
        )

        return {
            "success": True,
            "message": "Instance created, container is starting",
            "instance_id": instance_id,
            "websocket_logs": f"/api/logs/{request.connector_type}_{instance_id}"
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
async def update_instance(connector: str, instance_id: str, request: CreateInstanceRequest):
    """Update instance configuration and restart container"""
    try:
        # Load existing configuration to preserve metadata
        existing = config_service.load_instance_with_secrets(connector, instance_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Instance not found")

        # Prepare updated instance configuration (full replacement)
        instance_config = {
            "instance_id": instance_id,  # Keep the same ID
            "instance_type": existing.get("instance_type", "device"),
            "connector_type": connector,
            "friendly_name": request.friendly_name,
            "connection": request.config,
            "devices": request.devices,  # Complete replacement
            "enabled": request.enabled,
            "update_interval": request.update_interval,
            "created_at": existing.get("created_at", datetime.now().isoformat()),  # Preserve original
            "updated_at": datetime.now().isoformat()  # Update timestamp
        }

        # Maintain backwards compatibility: expose connection keys at top-level
        if isinstance(request.config, dict):
            for key, value in request.config.items():
                if key not in instance_config:
                    instance_config[key] = value

        # Save updated configuration with secrets
        config_service.save_instance_with_secrets(
            connector,
            instance_id,
            instance_config,
            request.secrets
        )

        # Restart container to apply new configuration
        container_name = f"iot2mqtt_{connector}_{instance_id}"
        restart_success = docker_service.restart_container(container_name)

        return {
            "success": True,
            "message": "Instance updated and container restarted" if restart_success
                       else "Instance updated but container restart failed",
            "container_restarted": restart_success,
            "warning": not restart_success
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
