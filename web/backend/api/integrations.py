"""
Integrations API endpoints
Управление настроенными интеграциями и их инстансами
"""

import json
import logging
import docker
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from services.config_service import ConfigService
from services.docker_service import DockerService
from services.mqtt_service import MQTTService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations", tags=["Integrations"])

# Services
config_service = ConfigService()
docker_service = DockerService()
mqtt_service = None  # Will be initialized from main.py


class IntegrationInstance(BaseModel):
    """Integration instance model"""
    instance_id: str
    friendly_name: str
    integration: str
    status: str = "unknown"  # connected, error, offline, configuring
    device_count: int = 0
    last_seen: Optional[str] = None
    created_at: str
    config: Dict[str, Any] = {}


class ConfiguredIntegration(BaseModel):
    """Configured integration summary"""
    name: str
    display_name: str
    instances_count: int
    status: str  # connected, error, offline, configuring
    last_seen: Optional[str] = None
    instances: List[IntegrationInstance] = []


@router.get("/", response_model=List[ConfiguredIntegration])
async def get_configured_integrations():
    """Get list of all configured integrations with their instances"""
    try:
        configured_integrations = {}
        
        # Scan all connector directories for instances
        connectors_path = config_service.connectors_path
        if not connectors_path.exists():
            return []
        
        for connector_dir in connectors_path.iterdir():
            if not connector_dir.is_dir() or connector_dir.name.startswith('_'):
                continue
                
            instances_path = config_service.instances_path / connector_dir.name
            if not instances_path.exists():
                continue

            # Read setup.json for display name
            setup_path = connector_dir / "setup.json"
            display_name = connector_dir.name
            if setup_path.exists():
                try:
                    with open(setup_path, 'r') as f:
                        setup_data = json.load(f)
                        display_name = setup_data.get("display_name", connector_dir.name)
                except:
                    pass
            
            # Get all instances for this connector
            instances = []
            for instance_file in instances_path.glob("*.json"):
                try:
                    with open(instance_file, 'r') as f:
                        instance_config = json.load(f)
                    
                    # Get container status
                    container_status = await get_container_status(
                        connector_dir.name, 
                        instance_file.stem
                    )
                    
                    instance = IntegrationInstance(
                        instance_id=instance_file.stem,
                        friendly_name=instance_config.get("friendly_name", instance_file.stem),
                        integration=connector_dir.name,
                        status=container_status,
                        device_count=len(instance_config.get("devices", [])),
                        created_at=instance_config.get("created_at", datetime.now().isoformat()),
                        config=instance_config
                    )
                    instances.append(instance)
                except Exception as e:
                    logger.error(f"Failed to load instance {instance_file}: {e}")
                    continue
            
            if instances:
                # Determine overall integration status
                statuses = [inst.status for inst in instances]
                overall_status = "connected"
                if "error" in statuses:
                    overall_status = "error"
                elif "offline" in statuses:
                    overall_status = "offline"
                elif "configuring" in statuses:
                    overall_status = "configuring"
                
                configured_integrations[connector_dir.name] = ConfiguredIntegration(
                    name=connector_dir.name,
                    display_name=display_name,
                    instances_count=len(instances),
                    status=overall_status,
                    last_seen=max([inst.last_seen for inst in instances if inst.last_seen], default=None),
                    instances=instances
                )
        
        return list(configured_integrations.values())
        
    except Exception as e:
        logger.error(f"Failed to get configured integrations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{integration_name}/instances", response_model=List[IntegrationInstance])
async def get_integration_instances(integration_name: str):
    """Get all instances for a specific integration"""
    try:
        instances_path = config_service.instances_path / integration_name
        if not instances_path.exists():
            return []
        
        instances = []
        for instance_file in instances_path.glob("*.json"):
            try:
                with open(instance_file, 'r') as f:
                    instance_config = json.load(f)
                
                container_status = await get_container_status(
                    integration_name, 
                    instance_file.stem
                )
                
                instance = IntegrationInstance(
                    instance_id=instance_file.stem,
                    friendly_name=instance_config.get("friendly_name", instance_file.stem),
                    integration=integration_name,
                    status=container_status,
                    device_count=len(instance_config.get("devices", [])),
                    created_at=instance_config.get("created_at", datetime.now().isoformat()),
                    config=instance_config
                )
                instances.append(instance)
            except Exception as e:
                logger.error(f"Failed to load instance {instance_file}: {e}")
                continue
        
        return instances
        
    except Exception as e:
        logger.error(f"Failed to get instances for {integration_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instances/{instance_id}")
async def get_instance_details(instance_id: str):
    """Get detailed information about a specific instance"""
    try:
        # Find the instance file across all connectors
        instances_root = config_service.instances_path

        for connector_dir in config_service.connectors_path.iterdir():
            if not connector_dir.is_dir() or connector_dir.name.startswith('_'):
                continue

            instance_file = instances_root / connector_dir.name / f"{instance_id}.json"
            if instance_file.exists():
                with open(instance_file, 'r') as f:
                    instance_config = json.load(f)
                
                container_status = await get_container_status(
                    connector_dir.name, 
                    instance_id
                )
                
                return {
                    "instance_id": instance_id,
                    "integration": connector_dir.name,
                    "friendly_name": instance_config.get("friendly_name", instance_id),
                    "status": container_status,
                    "config": instance_config,
                    "created_at": instance_config.get("created_at", datetime.now().isoformat())
                }
        
        raise HTTPException(status_code=404, detail=f"Instance {instance_id} not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get instance details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/instances/{instance_id}/start")
async def start_instance(instance_id: str):
    """Start a stopped instance"""
    try:
        # Find the integration for this instance
        integration_name = await find_integration_for_instance(instance_id)
        if not integration_name:
            raise HTTPException(status_code=404, detail=f"Instance {instance_id} not found")
        
        # Start the container
        docker_client = docker.DockerClient(base_url='unix:///var/run/docker.sock')
        container_name = f"iot2mqtt_{integration_name}_{instance_id}"
        
        try:
            container = docker_client.containers.get(container_name)
            if container.status != "running":
                container.start()
                logger.info(f"Started container {container_name}")
        except docker.errors.NotFound:
            # Container doesn't exist, create and start it
            await create_container_for_instance(integration_name, instance_id)
        
        return {"status": "success", "message": f"Instance {instance_id} started"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/instances/{instance_id}/stop")
async def stop_instance(instance_id: str):
    """Stop a running instance"""
    try:
        integration_name = await find_integration_for_instance(instance_id)
        if not integration_name:
            raise HTTPException(status_code=404, detail=f"Instance {instance_id} not found")
        
        docker_client = docker.DockerClient(base_url='unix:///var/run/docker.sock')
        container_name = f"iot2mqtt_{integration_name}_{instance_id}"
        
        try:
            container = docker_client.containers.get(container_name)
            if container.status == "running":
                container.stop()
                logger.info(f"Stopped container {container_name}")
        except docker.errors.NotFound:
            pass  # Container doesn't exist, that's fine
        
        return {"status": "success", "message": f"Instance {instance_id} stopped"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/instances/{instance_id}/restart")
async def restart_instance(instance_id: str):
    """Restart an instance"""
    try:
        await stop_instance(instance_id)
        await start_instance(instance_id)
        
        return {"status": "success", "message": f"Instance {instance_id} restarted"}
        
    except Exception as e:
        logger.error(f"Failed to restart instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mqtt/clear-all")
async def clear_all_mqtt_topics():
    """
    Clear ALL IoT2MQTT topics from MQTT broker.
    WARNING: This removes all data and cannot be undone!
    """
    try:
        if not mqtt_service or not mqtt_service.connected:
            raise HTTPException(status_code=503, detail="MQTT service not available")
        
        # Clear all topics
        success = mqtt_service.clear_all_iot2mqtt_topics()
        
        if success:
            return {
                "status": "success",
                "message": "All IoT2MQTT topics cleared from MQTT broker"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to clear MQTT topics")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear all MQTT topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mqtt/clear-instance/{instance_id}")
async def clear_instance_mqtt_topics(instance_id: str):
    """Clear all MQTT topics for a specific instance"""
    try:
        if not mqtt_service or not mqtt_service.connected:
            raise HTTPException(status_code=503, detail="MQTT service not available")
        
        # Clear instance topics
        success = mqtt_service.clear_instance_topics(instance_id)
        
        if success:
            return {
                "status": "success",
                "message": f"All MQTT topics cleared for instance {instance_id}"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to clear MQTT topics")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear MQTT topics for {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/instances/{instance_id}")
async def delete_instance(instance_id: str):
    """Delete an instance completely (container, config, MQTT topics)"""
    try:
        integration_name = await find_integration_for_instance(instance_id)
        if not integration_name:
            raise HTTPException(status_code=404, detail=f"Instance {instance_id} not found")
        
        # 1. Stop and remove Docker container
        docker_client = docker.DockerClient(base_url='unix:///var/run/docker.sock')
        container_name = f"iot2mqtt_{integration_name}_{instance_id}"
        
        try:
            container = docker_client.containers.get(container_name)
            container.stop()
            container.remove(force=True)
            logger.info(f"Removed container {container_name}")
        except docker.errors.NotFound:
            pass
        
        # 2. Delete configuration file
        config_file = config_service.instances_path / integration_name / f"{instance_id}.json"
        if config_file.exists():
            config_file.unlink()
            logger.info(f"Deleted config file {config_file}")
        
        # 3. Clear MQTT topics for this instance
        if mqtt_service and mqtt_service.connected:
            try:
                # Use the comprehensive cleanup method
                mqtt_service.clear_instance_topics(instance_id)
                logger.info(f"Cleared all MQTT topics for instance {instance_id}")
            except Exception as e:
                logger.warning(f"Failed to clear MQTT topics for {instance_id}: {e}")
        else:
            logger.warning("MQTT service not available for topic cleanup")
        
        return {
            "status": "success", 
            "message": f"Instance {instance_id} deleted completely"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def get_container_status(integration_name: str, instance_id: str) -> str:
    """Get the status of a container"""
    try:
        docker_client = docker.DockerClient(base_url='unix:///var/run/docker.sock')
        container_name = f"iot2mqtt_{integration_name}_{instance_id}"
        
        try:
            container = docker_client.containers.get(container_name)
            status = container.status.lower()
            
            if status == "running":
                return "connected"
            elif status in ["stopped", "exited"]:
                return "offline"
            elif status in ["restarting", "created"]:
                return "configuring"
            else:
                return "error"
                
        except docker.errors.NotFound:
            return "offline"
            
    except Exception as e:
        logger.error(f"Failed to get container status: {e}")
        return "error"


async def find_integration_for_instance(instance_id: str) -> Optional[str]:
    """Find which integration an instance belongs to"""
    for connector_dir in config_service.connectors_path.iterdir():
        if not connector_dir.is_dir() or connector_dir.name.startswith('_'):
            continue

        instance_file = config_service.instances_path / connector_dir.name / f"{instance_id}.json"
        if instance_file.exists():
            return connector_dir.name
    
    return None


async def create_container_for_instance(integration_name: str, instance_id: str):
    """Create and start a container for an instance"""
    try:
        # Load instance configuration
        config_file = config_service.instances_path / integration_name / f"{instance_id}.json"
        if not config_file.exists():
            raise HTTPException(status_code=404, detail="Instance configuration not found")
        
        with open(config_file, 'r') as f:
            instance_config = json.load(f)
        
        # Use Docker service to create container
        docker_service.create_or_update_container(
            integration_name,
            instance_id,
            instance_config
        )
        
        logger.info(f"Created container for {integration_name}/{instance_id}")
        
    except Exception as e:
        logger.error(f"Failed to create container: {e}")
        raise
