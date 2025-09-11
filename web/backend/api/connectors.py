"""
Connectors/Integrations API endpoints
"""

import os
import asyncio
import json
import docker
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from services.config_service import ConfigService
from services.docker_service import DockerService
from models.schemas import ConnectorInfo, SetupSchema, SetupField

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Integrations"])

# Services
config_service = ConfigService()
docker_service = DockerService()

# Active discovery sessions
discovery_sessions = {}


class DiscoveryRequest(BaseModel):
    """Discovery request parameters"""
    timeout: int = 30
    network_mode: str = "host"
    

class ValidateRequest(BaseModel):
    """Configuration validation request"""
    config: Dict[str, Any]


@router.get("/api/integrations", response_model=List[ConnectorInfo])
async def list_integrations():
    """List all available integrations with branding"""
    try:
        connectors = config_service.list_connectors()
        
        # Add branding information
        for connector in connectors:
            connector["branding"] = config_service.get_connector_branding(connector["name"])
            
        return connectors
    except Exception as e:
        logger.error(f"Failed to list integrations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/integrations/{name}/meta")
async def get_integration_meta(name: str):
    """Get integration metadata including setup schema and branding"""
    try:
        setup = config_service.get_connector_setup(name)
        if not setup:
            raise HTTPException(status_code=404, detail="Integration not found")
        
        # Add branding if not present
        if "branding" not in setup:
            setup["branding"] = config_service.get_connector_branding(name)
        
        # Check for icon file
        icon_path = config_service.connectors_path / name / "icon.svg"
        if icon_path.exists():
            setup["icon_url"] = f"/api/integrations/{name}/icon"
        
        return setup
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get integration meta: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/integrations/{name}/icon")
async def get_integration_icon(name: str):
    """Get integration icon"""
    icon_path = config_service.connectors_path / name / "icon.svg"
    
    if not icon_path.exists():
        # Return default icon
        default_icon = Path("/app/frontend/dist/assets/default-icon.svg")
        if default_icon.exists():
            return FileResponse(default_icon, media_type="image/svg+xml")
        raise HTTPException(status_code=404, detail="Icon not found")
    
    return FileResponse(icon_path, media_type="image/svg+xml")


@router.post("/api/integrations/{name}/discover")
async def start_discovery(name: str, request: DiscoveryRequest, background_tasks: BackgroundTasks):
    """Start device discovery for an integration"""
    try:
        # Check if discovery is supported
        setup = config_service.get_connector_setup(name)
        if not setup or "discovery" not in setup:
            raise HTTPException(status_code=400, detail="Discovery not supported for this integration")
        
        discovery_config = setup["discovery"]
        
        # Generate discovery session ID
        import uuid
        session_id = str(uuid.uuid4())
        
        # Start discovery in background
        background_tasks.add_task(
            run_discovery,
            name,
            session_id,
            discovery_config,
            request.network_mode,
            request.timeout
        )
        
        return {
            "session_id": session_id,
            "status": "started",
            "websocket_url": f"/api/discovery/{session_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start discovery: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def run_discovery(connector_name: str, session_id: str, 
                       discovery_config: dict, network_mode: str, timeout: int):
    """Run discovery in Docker container"""
    global discovery_sessions
    
    discovery_sessions[session_id] = {
        "status": "running",
        "devices": [],
        "progress": 0,
        "logs": []
    }
    
    try:
        # Build image if needed
        image_tag = f"iot2mqtt/{connector_name}:latest"
        
        # Check if image exists
        docker_client = docker.from_env()
        try:
            docker_client.images.get(image_tag)
        except docker.errors.ImageNotFound:
            logger.info(f"Building image for {connector_name}")
            docker_service.build_image(connector_name, image_tag)
        
        # Run discovery container
        container = docker_client.containers.run(
            image_tag,
            command="python -m connector discover",
            network_mode=network_mode,  # Critical for network scanning!
            remove=False,
            detach=True,
            stdout=True,
            stderr=True,
            environment={
                "DISCOVERY_MODE": "true",
                "DISCOVERY_TIMEOUT": str(timeout)
            }
        )
        
        # Monitor container output
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            # Check container status
            container.reload()
            if container.status != "running":
                break
            
            # Read logs
            logs = container.logs(tail=10).decode('utf-8')
            
            # Parse discovery output (expecting JSON lines)
            for line in logs.split('\n'):
                if line.strip():
                    try:
                        data = json.loads(line)
                        if "device" in data:
                            discovery_sessions[session_id]["devices"].append(data["device"])
                        if "progress" in data:
                            discovery_sessions[session_id]["progress"] = data["progress"]
                    except json.JSONDecodeError:
                        discovery_sessions[session_id]["logs"].append(line)
            
            await asyncio.sleep(1)
        
        # Cleanup container
        container.stop()
        container.remove()
        
        discovery_sessions[session_id]["status"] = "completed"
        discovery_sessions[session_id]["progress"] = 100
        
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        discovery_sessions[session_id]["status"] = "failed"
        discovery_sessions[session_id]["error"] = str(e)


@router.websocket("/api/discovery/{session_id}")
async def discovery_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for discovery progress"""
    await websocket.accept()
    
    if session_id not in discovery_sessions:
        await websocket.send_json({
            "error": "Invalid session ID"
        })
        await websocket.close()
        return
    
    try:
        last_update = {}
        
        while discovery_sessions[session_id]["status"] == "running":
            current_state = discovery_sessions[session_id].copy()
            
            # Send updates only if changed
            if current_state != last_update:
                await websocket.send_json(current_state)
                last_update = current_state
            
            await asyncio.sleep(0.5)
        
        # Send final state
        await websocket.send_json(discovery_sessions[session_id])
        
    except WebSocketDisconnect:
        logger.info(f"Discovery WebSocket disconnected for session {session_id}")
    finally:
        # Cleanup session after some time
        await asyncio.sleep(60)
        if session_id in discovery_sessions:
            del discovery_sessions[session_id]


@router.post("/api/integrations/{name}/validate")
async def validate_configuration(name: str, request: ValidateRequest):
    """Validate integration configuration"""
    try:
        setup = config_service.get_connector_setup(name)
        if not setup:
            raise HTTPException(status_code=404, detail="Integration not found")
        
        errors = []
        warnings = []
        
        # Validate required fields
        if "fields" in setup:
            for field in setup["fields"]:
                field_name = field["name"]
                field_required = field.get("required", False)
                
                if field_required and field_name not in request.config:
                    errors.append(f"Required field '{field_name}' is missing")
                
                # Validate field value if present
                if field_name in request.config:
                    value = request.config[field_name]
                    
                    # Type validation
                    field_type = field.get("type")
                    if field_type == "number" and not isinstance(value, (int, float)):
                        errors.append(f"Field '{field_name}' must be a number")
                    elif field_type == "checkbox" and not isinstance(value, bool):
                        errors.append(f"Field '{field_name}' must be a boolean")
                    
                    # Pattern validation
                    if "validation" in field and "pattern" in field["validation"]:
                        import re
                        pattern = field["validation"]["pattern"]
                        if isinstance(value, str) and not re.match(pattern, value):
                            errors.append(f"Field '{field_name}' does not match required pattern")
                    
                    # Range validation for numbers
                    if field_type == "number":
                        if "min" in field and value < field["min"]:
                            errors.append(f"Field '{field_name}' must be >= {field['min']}")
                        if "max" in field and value > field["max"]:
                            errors.append(f"Field '{field_name}' must be <= {field['max']}")
        
        # Check for unknown fields
        if "fields" in setup:
            known_fields = {f["name"] for f in setup["fields"]}
            for key in request.config.keys():
                if key not in known_fields and not key.startswith("_"):
                    warnings.append(f"Unknown field '{key}'")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/connectors/available")
async def get_available_connectors():
    """Get list of available connectors with manifest data"""
    connectors = []
    
    # Scan connectors directory
    connectors_path = Path("/app/connectors")
    if not connectors_path.exists():
        return []
    
    for connector_dir in connectors_path.iterdir():
        if connector_dir.is_dir() and not connector_dir.name.startswith('_'):
            # Check for manifest.json (new format)
            manifest_file = connector_dir / "manifest.json"
            if manifest_file.exists():
                with open(manifest_file, 'r') as f:
                    manifest = json.load(f)
                    
                connectors.append({
                    "name": connector_dir.name,
                    "display_name": manifest.get("name", connector_dir.name),
                    "version": manifest.get("version", "1.0.0"),
                    "author": manifest.get("author", "Unknown"),
                    "description": f"Integration for {manifest.get('name', connector_dir.name)} devices",
                    "branding": manifest.get("branding"),
                    "discovery": manifest.get("discovery"),
                    "manual_config": manifest.get("manual_config"),
                    "capabilities": manifest.get("capabilities", [])
                })
            # Fallback to old setup.json format
            elif (connector_dir / "setup.json").exists():
                setup_file = connector_dir / "setup.json"
                with open(setup_file, 'r') as f:
                    setup_data = json.load(f)
                    
                connectors.append({
                    "name": connector_dir.name,
                    "display_name": setup_data.get("display_name", connector_dir.name),
                    "version": setup_data.get("version", "1.0.0"),
                    "author": setup_data.get("author", "Unknown"),
                    "description": setup_data.get("description", ""),
                    "branding": {
                        "icon": "📦",
                        "category": "general"
                    },
                    "discovery": {
                        "supported": False
                    }
                })
    
    return connectors