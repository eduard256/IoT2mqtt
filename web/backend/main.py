"""
IoT2MQTT Web Interface - FastAPI Backend
"""

import os
import sys
from pathlib import Path
from typing import Optional, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import socketio
from jose import JWTError, jwt
from passlib.context import CryptContext
import uvicorn

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from models.schemas import *
from services.config_service import ConfigService
from services.docker_service import DockerService
from services.mqtt_service import MQTTService
from api import auth, mqtt, connectors, instances, devices, docker, discovery, integrations, tools
from services.secrets_manager import SecretsManager

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# Services
config_service = ConfigService()
docker_service = DockerService()
mqtt_service = None

# Socket.IO
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=False,
    engineio_logger=False
)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security
security = HTTPBearer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global mqtt_service
    
    # Initialize MQTT if configured
    mqtt_config = config_service.get_mqtt_config()
    if mqtt_config.get("host"):
        mqtt_service = MQTTService(mqtt_config)
        if mqtt_service.connect():
            logger.info("Connected to MQTT broker")
            # Share mqtt_service with integrations module
            integrations.mqtt_service = mqtt_service
        else:
            logger.warning("Failed to connect to MQTT broker")
    
    yield
    
    # Cleanup
    if mqtt_service:
        mqtt_service.disconnect()


# Create FastAPI app
app = FastAPI(
    title="IoT2MQTT Web Interface",
    description="Beautiful web interface for IoT2MQTT",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(connectors.router)
app.include_router(instances.router)
app.include_router(devices.router)
app.include_router(docker.router)
app.include_router(discovery.router)
app.include_router(integrations.router)
app.include_router(tools.router)

# Static files will be mounted after API routes

# Socket.IO app
socket_app = socketio.ASGIApp(sio, app)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def verify_access_key(key: str) -> bool:
    """Verify access key"""
    stored_key = config_service.get_access_key()
    
    # If no key is set, this is first time setup
    if not stored_key:
        # Set the provided key as the access key
        config_service.set_access_key(pwd_context.hash(key))
        return True
    
    # Verify against stored key
    return pwd_context.verify(key, stored_key)


# API Routes


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "mqtt_connected": mqtt_service.connected if mqtt_service else False,
        "docker_available": docker_service.client.ping() if docker_service and docker_service.client else False
    }


@app.post("/api/auth/login", response_model=AuthResponse)
async def login(request: AuthRequest):
    """Login with access key"""
    if not verify_access_key(request.key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access key"
        )
    
    # Create access token
    access_token = create_access_token(
        data={"sub": "user"},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return AuthResponse(
        success=True,
        message="Login successful",
        token=access_token
    )


@app.get("/api/auth/check")
async def check_auth(token_data=Depends(verify_token)):
    """Check if authenticated"""
    return {"authenticated": True, "user": token_data.get("sub")}


@app.get("/api/setup/status")
async def setup_status():
    """Check setup status"""
    has_key = config_service.get_access_key() is not None
    mqtt_config = config_service.get_mqtt_config()
    has_mqtt = bool(mqtt_config.get("host"))
    
    return {
        "has_access_key": has_key,
        "has_mqtt_config": has_mqtt,
        "setup_complete": has_key and has_mqtt
    }


@app.get("/api/mqtt/status")
async def get_mqtt_status(token_data=Depends(verify_token)):
    """Get MQTT connection status"""
    mqtt_config = config_service.get_mqtt_config()
    return {
        "connected": mqtt_service.connected if mqtt_service else False,
        "broker": mqtt_config.get("host", "Not configured"),
        "port": mqtt_config.get("port", 1883),
        "topics_count": len(mqtt_service.topic_cache) if mqtt_service else 0,
        "base_topic": mqtt_config.get("base_topic", "IoT2mqtt")
    }


@app.get("/api/mqtt/config", response_model=MQTTConfig)
async def get_mqtt_config(token_data=Depends(verify_token)):
    """Get MQTT configuration"""
    config = config_service.get_mqtt_config()
    # Mask password
    if config.get("password"):
        config["password"] = "***HIDDEN***"
    return MQTTConfig(**config)


@app.post("/api/mqtt/config")
async def save_mqtt_config(config: MQTTConfig, token_data=Depends(verify_token)):
    """Save MQTT configuration"""
    config_dict = config.dict()
    
    # Don't overwrite password if masked
    if config_dict.get("password") == "***HIDDEN***":
        existing = config_service.get_mqtt_config()
        config_dict["password"] = existing.get("password", "")
    
    config_service.save_mqtt_config(config_dict)
    
    # Reconnect MQTT with new config
    global mqtt_service
    if mqtt_service:
        mqtt_service.disconnect()
    
    mqtt_service = MQTTService(config_dict)
    if mqtt_service.connect():
        return {"success": True, "message": "MQTT configuration saved and connected"}
    else:
        return {"success": False, "message": "Configuration saved but connection failed"}


@app.post("/api/mqtt/test")
async def test_mqtt_connection(config: MQTTConfig):
    """Test MQTT connection"""
    import socket
    
    try:
        # Test TCP connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((config.host, config.port))
        sock.close()
        
        if result == 0:
            return {"success": True, "message": "Connection successful"}
        else:
            return {"success": False, "message": f"Cannot connect to {config.host}:{config.port}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/api/connectors", response_model=List[ConnectorInfo])
async def list_connectors(token_data=Depends(verify_token)):
    """List available connectors"""
    connectors = config_service.list_connectors()
    return [ConnectorInfo(**c) for c in connectors]


@app.get("/api/connectors/{connector_name}/setup")
async def get_connector_setup(connector_name: str, token_data=Depends(verify_token)):
    """Get connector setup schema"""
    setup = config_service.get_connector_setup(connector_name)
    if not setup:
        raise HTTPException(status_code=404, detail="Connector setup not found")
    return setup


@app.get("/api/instances", response_model=List[InstanceConfig])
async def list_instances(connector: Optional[str] = None, token_data=Depends(verify_token)):
    """List instances"""
    instances = config_service.list_instances(connector)
    return [InstanceConfig(**i) for i in instances]


@app.get("/api/instances/{connector}/{instance_id}", response_model=InstanceConfig)
async def get_instance(connector: str, instance_id: str, token_data=Depends(verify_token)):
    """Get instance configuration"""
    instance = config_service.get_instance_config(connector, instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    return InstanceConfig(**instance)


@app.post("/api/instances/{connector}")
async def create_instance(connector: str, config: InstanceConfig, token_data=Depends(verify_token)):
    """Create new instance"""
    # Save instance configuration
    config_service.save_instance_config(connector, config.instance_id, config.dict())
    
    # Update docker-compose.yml
    docker_service.update_docker_compose(connector, config.instance_id, config.dict())
    
    # Build and start container
    container_id = docker_service.create_container(connector, config.instance_id, config.dict())
    
    if container_id:
        return {"success": True, "message": "Instance created", "container_id": container_id}
    else:
        return {"success": False, "message": "Failed to create container"}


@app.delete("/api/instances/{connector}/{instance_id}")
async def delete_instance(connector: str, instance_id: str, token_data=Depends(verify_token)):
    """Delete instance"""
    # Stop and remove container
    container_name = f"iot2mqtt_{connector}_{instance_id}"
    container = docker_service.get_container(container_name)
    if container:
        docker_service.stop_container(container_name)
        docker_service.remove_container(container_name)
    
    # Delete configuration
    if config_service.delete_instance_config(connector, instance_id):
        return {"success": True, "message": "Instance deleted"}
    else:
        return {"success": False, "message": "Instance not found"}


@app.get("/api/mqtt/topics")
async def get_mqtt_topics(filter: Optional[str] = None, token_data=Depends(verify_token)):
    """Get MQTT topics as flat list"""
    if not mqtt_service:
        raise HTTPException(status_code=503, detail="MQTT not connected")
    
    topics = mqtt_service.get_topics_list()
    
    # Apply filter if provided
    if filter:
        topics = [t for t in topics if filter.lower() in t["topic"].lower()]
    
    return topics


@app.post("/api/mqtt/publish")
async def publish_mqtt(message: MQTTMessage, token_data=Depends(verify_token)):
    """Publish MQTT message"""
    if not mqtt_service:
        raise HTTPException(status_code=503, detail="MQTT not connected")
    
    if mqtt_service.publish(message.topic, message.payload, message.retain, message.qos):
        return {"success": True, "message": "Message published"}
    else:
        return {"success": False, "message": "Failed to publish message"}


@app.get("/api/devices/{instance_id}")
async def list_devices(instance_id: str, token_data=Depends(verify_token)):
    """List devices for instance"""
    if not mqtt_service:
        raise HTTPException(status_code=503, detail="MQTT not connected")
    
    devices = mqtt_service.get_instance_devices(instance_id)
    device_states = []
    
    for device_id in devices:
        state = mqtt_service.get_device_state(instance_id, device_id)
        if state:
            device_states.append({
                "device_id": device_id,
                "instance_id": instance_id,
                "state": state
            })
    
    return device_states


@app.post("/api/devices/{instance_id}/{device_id}/command")
async def send_device_command(
    instance_id: str,
    device_id: str,
    command: DeviceCommand,
    token_data=Depends(verify_token)
):
    """Send command to device"""
    if not mqtt_service:
        raise HTTPException(status_code=503, detail="MQTT not connected")
    
    cmd_id = mqtt_service.send_command(instance_id, device_id, command.command)
    return {"success": True, "command_id": cmd_id}


@app.get("/api/system/status", response_model=SystemStatus)
async def get_system_status(token_data=Depends(verify_token)):
    """Get system status"""
    docker_stats = docker_service.get_system_stats()
    instances = config_service.list_instances()
    
    devices_count = 0
    for instance in instances:
        devices_count += len(instance.get("devices", []))
    
    return SystemStatus(
        mqtt_connected=mqtt_service.connected if mqtt_service else False,
        docker_available=True,
        instances_count=len(instances),
        devices_count=devices_count,
        containers_running=docker_stats.get("containers", {}).get("running", 0),
        containers_total=docker_stats.get("containers", {}).get("total", 0)
    )


# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    
    # Add handler for MQTT updates
    async def mqtt_handler(message):
        try:
            await websocket.send_json(message)
        except:
            pass
    
    if mqtt_service:
        mqtt_service.add_websocket_handler(mqtt_handler)
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        if mqtt_service:
            mqtt_service.remove_websocket_handler(mqtt_handler)


# WebSocket endpoint for container logs with authentication
@app.websocket("/ws/logs/{container_id}")
async def container_logs_websocket(websocket: WebSocket, container_id: str, token: str = Query(...)):
    """WebSocket endpoint for streaming container logs with authentication using aiodocker"""
    # Verify token
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    await websocket.accept()
    logger.info(f"Container logs WebSocket connected for {container_id}")
    
    import aiodocker
    import asyncio
    
    docker_client = None
    container = None
    
    try:
        # Create async docker client
        docker_client = aiodocker.Docker()
        
        # Check if container exists
        try:
            container = await docker_client.containers.get(container_id)
            container_info = await container.show()
            logger.info(f"Found container: {container_info['Name']}")
        except aiodocker.exceptions.DockerError:
            logger.error(f"Container {container_id} not found")
            await websocket.send_json({
                "error": f"Container {container_id} not found",
                "timestamp": datetime.now().isoformat(),
                "level": "error"
            })
            await websocket.close(code=1008, reason="Container not found")
            return
        
        logger.info(f"Starting real-time log stream for container {container_id}")
        
        # Stream logs asynchronously
        log_count = 0
        async for line in container.log(stdout=True, stderr=True, follow=True, tail=100):
            # Parse log line
            log_text = line.decode('utf-8') if isinstance(line, bytes) else str(line)
            
            # Determine log level from content
            log_level = "info"
            log_lower = log_text.lower()
            if "error" in log_lower or "exception" in log_lower:
                log_level = "error"
            elif "warning" in log_lower or "warn" in log_lower:
                log_level = "warning"
            elif "success" in log_lower or "connected" in log_lower:
                log_level = "success"
            elif "debug" in log_lower:
                log_level = "debug"
            
            # Send log entry
            await websocket.send_json({
                "timestamp": datetime.now().isoformat(),
                "level": log_level,
                "content": log_text.strip()
            })
            
            log_count += 1
            if log_count % 50 == 0:
                logger.debug(f"Sent {log_count} log entries for {container_id}")
            
    except WebSocketDisconnect:
        logger.info(f"Container logs WebSocket disconnected for {container_id}")
    except asyncio.CancelledError:
        logger.info(f"Log streaming cancelled for {container_id}")
    except Exception as e:
        logger.error(f"Error streaming logs for {container_id}: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "level": "error"
            })
            await websocket.close(code=1011, reason="Internal error")
        except:
            pass
    finally:
        # Clean up
        if docker_client:
            await docker_client.close()
        logger.info(f"Cleaned up resources for {container_id}")


# WebSocket endpoint for MQTT Explorer with authentication
@app.websocket("/ws/mqtt")
async def mqtt_websocket(websocket: WebSocket, token: str = Query(...)):
    """WebSocket endpoint for MQTT Explorer with authentication"""
    # Verify token
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    await websocket.accept()
    logger.info("MQTT WebSocket connected")
    
    # Subscribe to all topics for explorer
    if mqtt_service:
        mqtt_service.subscribe("#")
    
    # Handler for MQTT messages
    async def mqtt_message_handler(topic: str, payload: Any, retained: bool = False):
        try:
            if payload is None:
                # Topic deletion
                await websocket.send_json({
                    "type": "delete",
                    "topic": topic
                })
            else:
                await websocket.send_json({
                    "type": "update",
                    "topic": topic,
                    "value": payload,
                    "timestamp": datetime.now().isoformat(),
                    "retained": retained
                })
        except:
            pass
    
    # Add handler if MQTT is connected
    if mqtt_service:
        mqtt_service.add_websocket_handler(mqtt_message_handler)
        
        # Send initial topics list
        try:
            topics = mqtt_service.get_topics_list()
            await websocket.send_json({
                "type": "topics",
                "data": topics
            })
        except:
            pass
    
    try:
        while True:
            # Receive commands from client
            data = await websocket.receive_json()
            
            if data.get("action") == "subscribe" and mqtt_service:
                topic = data.get("topic")
                if topic:
                    mqtt_service.subscribe(topic)
                    await websocket.send_json({
                        "type": "subscribed",
                        "topic": topic
                    })
                    
            elif data.get("action") == "unsubscribe" and mqtt_service:
                topic = data.get("topic")
                if topic:
                    mqtt_service.unsubscribe(topic)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "topic": topic
                    })
                    
            elif data.get("action") == "publish" and mqtt_service:
                topic = data.get("topic")
                payload = data.get("payload")
                qos = data.get("qos", 0)
                retain = data.get("retain", False)
                if topic is not None and payload is not None:
                    mqtt_service.publish(topic, payload, qos, retain)
                    await websocket.send_json({
                        "type": "published",
                        "topic": topic
                    })
                    
    except WebSocketDisconnect:
        logger.info("MQTT WebSocket disconnected")
        if mqtt_service:
            mqtt_service.remove_websocket_handler(mqtt_message_handler)


# Socket.IO events
@sio.event
async def connect(sid, environ):
    """Socket.IO connection"""
    logger.info(f"Socket.IO client connected: {sid}")


@sio.event
async def disconnect(sid):
    """Socket.IO disconnection"""
    logger.info(f"Socket.IO client disconnected: {sid}")


@sio.event
async def subscribe_logs(sid, data):
    """Subscribe to container logs"""
    container_id = data.get("container_id")
    if container_id:
        # Start streaming logs
        async def stream_logs():
            for log in docker_service.get_container_logs(container_id, follow=True):
                await sio.emit("log", log, room=sid)
        
        sio.start_background_task(stream_logs)


# Mount static files for React app (in production)
# Important: Mount static files AFTER all API routes to avoid conflicts
if os.path.exists("/app/frontend/dist"):
    # Serve static assets
    if os.path.exists("/app/frontend/dist/assets"):
        app.mount("/assets", StaticFiles(directory="/app/frontend/dist/assets"), name="assets")
    
    # Mount icons directory for PWA icons
    if os.path.exists("/app/frontend/dist/icons"):
        app.mount("/icons", StaticFiles(directory="/app/frontend/dist/icons"), name="icons")
    
    # Serve root-level files (PWA icons, manifest, etc.)
    @app.get("/pwa-192x192.png")
    async def serve_pwa_192():
        return FileResponse("/app/frontend/dist/pwa-192x192.png")
    
    @app.get("/pwa-512x512.png")
    async def serve_pwa_512():
        return FileResponse("/app/frontend/dist/pwa-512x512.png")
    
    @app.get("/manifest.json")
    async def serve_manifest_json():
        return FileResponse("/app/frontend/dist/manifest.json")
    
    @app.get("/manifest.webmanifest")
    async def serve_manifest():
        return FileResponse("/app/frontend/dist/manifest.webmanifest")
    
    @app.get("/favicon.ico")
    async def serve_favicon():
        return FileResponse("/app/frontend/dist/favicon.ico")
    
    @app.get("/robots.txt")
    async def serve_robots():
        return FileResponse("/app/frontend/dist/robots.txt")
    
    # Service Worker files
    @app.get("/sw.js")
    async def serve_sw():
        return FileResponse("/app/frontend/dist/sw.js", media_type="application/javascript")
    
    @app.get("/registerSW.js")
    async def serve_register_sw():
        return FileResponse("/app/frontend/dist/registerSW.js", media_type="application/javascript")
    
    @app.get("/workbox-{version}.js")
    async def serve_workbox(version: str):
        return FileResponse(f"/app/frontend/dist/workbox-{version}.js", media_type="application/javascript")
    
    # Catch-all route for SPA - must be last!
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve React SPA for all non-API routes"""
        # Allow API and WebSocket routes to pass through
        if full_path.startswith("api/") or full_path.startswith("ws/") or full_path.startswith("socket.io/"):
            raise HTTPException(status_code=404, detail="Not found")
        
        # Serve actual files if they exist
        file_path = f"/app/frontend/dist/{full_path}"
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        
        # Otherwise serve index.html for client-side routing
        return FileResponse("/app/frontend/dist/index.html")


if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "main:socket_app",
        host="0.0.0.0",
        port=int(os.getenv("WEB_PORT", 8765)),
        reload=os.getenv("MODE") == "development",
        log_level="info"
    )
