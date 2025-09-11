"""
Docker management service
"""

import docker
import json
import yaml
import logging
from typing import Dict, Any, List, Optional, Generator
from pathlib import Path
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class DockerService:
    """Service for managing Docker containers"""
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path or os.getenv("IOT2MQTT_PATH", "/app"))
        try:
            # Connect to Docker via unix socket only
            self.client = docker.DockerClient(base_url='unix:///var/run/docker.sock')
            logger.info("Connected to Docker via unix socket")
            # Get host path from current container's mounts
            self.host_base_path = self._get_host_base_path()
            logger.info(f"Host base path: {self.host_base_path}")
        except Exception as e:
            logger.error(f"Failed to connect to Docker: {e}")
            self.client = None
            self.host_base_path = self.base_path
        self.prefix = "iot2mqtt_"
    
    def _get_host_base_path(self) -> Path:
        """Get host base path from current container's mounts"""
        try:
            # Try to get current container info
            import socket
            hostname = socket.gethostname()
            container = self.client.containers.get(hostname)
            
            # Look for /app/connectors mount to determine host path
            for mount in container.attrs.get('Mounts', []):
                if mount.get('Destination') == '/app/connectors':
                    source = mount.get('Source', '')
                    # Source is like /home/eduard/IoT2mqtt/connectors
                    # We need /home/eduard/IoT2mqtt
                    if source.endswith('/connectors'):
                        host_path = Path(source).parent
                        return host_path
            
            # Fallback - try to get from environment
            # If we're in container, PWD won't help, but we can try HOST_PATH if set
            host_path = os.getenv("HOST_IOT2MQTT_PATH")
            if host_path:
                return Path(host_path)
                
        except Exception as e:
            logger.warning(f"Could not determine host base path: {e}")
        
        # Fallback to base_path
        return self.base_path
        
    def list_containers(self, all: bool = True) -> List[Dict[str, Any]]:
        """List IoT2MQTT containers"""
        containers = []
        
        if not self.client:
            logger.warning("Docker client not connected")
            return containers
        
        try:
            for container in self.client.containers.list(all=all):
                # Filter by IoT2MQTT containers
                if container.name.startswith(self.prefix) or "iot2mqtt" in container.labels.get("com.docker.compose.project", ""):
                    info = {
                        "id": container.short_id,
                        "name": container.name,
                        "image": container.image.tags[0] if container.image.tags else container.image.short_id,
                        "status": container.status,
                        "state": container.attrs["State"]["Status"],
                        "created": container.attrs["Created"],
                        "ports": container.ports,
                        "labels": container.labels
                    }
                    
                    # Extract instance_id from container name
                    if container.name.startswith(self.prefix):
                        parts = container.name[len(self.prefix):].split('_', 1)
                        if len(parts) > 1:
                            info["connector_type"] = parts[0]
                            info["instance_id"] = parts[1]
                    
                    containers.append(info)
                    
        except Exception as e:
            logger.error(f"Error listing containers: {e}")
            
        return containers
    
    def get_container(self, container_id: str) -> Optional[docker.models.containers.Container]:
        """Get container by ID or name"""
        try:
            return self.client.containers.get(container_id)
        except docker.errors.NotFound:
            return None
        except Exception as e:
            logger.error(f"Error getting container {container_id}: {e}")
            return None
    
    def start_container(self, container_id: str) -> bool:
        """Start a container"""
        container = self.get_container(container_id)
        if container:
            try:
                container.start()
                return True
            except Exception as e:
                logger.error(f"Error starting container {container_id}: {e}")
        return False
    
    def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """Stop a container"""
        container = self.get_container(container_id)
        if container:
            try:
                container.stop(timeout=timeout)
                return True
            except Exception as e:
                logger.error(f"Error stopping container {container_id}: {e}")
        return False
    
    def restart_container(self, container_id: str, timeout: int = 10) -> bool:
        """Restart a container"""
        container = self.get_container(container_id)
        if container:
            try:
                container.restart(timeout=timeout)
                return True
            except Exception as e:
                logger.error(f"Error restarting container {container_id}: {e}")
        return False
    
    def remove_container(self, container_id: str, force: bool = False) -> bool:
        """Remove a container"""
        container = self.get_container(container_id)
        if container:
            try:
                container.remove(force=force)
                return True
            except Exception as e:
                logger.error(f"Error removing container {container_id}: {e}")
        return False
    
    def get_container_logs(self, container_id: str, lines: int = 100, 
                          since: Optional[datetime] = None,
                          follow: bool = False) -> Generator[Dict[str, Any], None, None]:
        """Get container logs"""
        container = self.get_container(container_id)
        if not container:
            return
        
        try:
            kwargs = {
                "tail": lines,
                "stream": True,
                "timestamps": True,
                "follow": follow
            }
            
            if since:
                kwargs["since"] = since
            
            for line in container.logs(**kwargs):
                if isinstance(line, bytes):
                    line = line.decode('utf-8')
                
                # Parse timestamp and log content
                parts = line.strip().split(' ', 1)
                if len(parts) == 2:
                    timestamp_str, content = parts
                    # Parse Docker timestamp format
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    except:
                        timestamp = datetime.now()
                else:
                    timestamp = datetime.now()
                    content = line.strip()
                
                # Determine log level
                content_lower = content.lower()
                if 'error' in content_lower or 'exception' in content_lower:
                    level = 'error'
                elif 'warning' in content_lower or 'warn' in content_lower:
                    level = 'warning'
                elif 'success' in content_lower or 'connected' in content_lower:
                    level = 'success'
                elif 'info' in content_lower:
                    level = 'info'
                elif 'debug' in content_lower:
                    level = 'debug'
                else:
                    level = 'info'
                
                yield {
                    "timestamp": timestamp.isoformat(),
                    "level": level,
                    "content": content
                }
                
        except Exception as e:
            logger.error(f"Error getting logs for container {container_id}: {e}")
    
    def build_image(self, connector_name: str, tag: Optional[str] = None) -> bool:
        """Build Docker image for connector"""
        connector_path = self.base_path / "connectors" / connector_name
        dockerfile = connector_path / "Dockerfile"
        
        if not dockerfile.exists():
            # Create default Dockerfile if not exists
            self._create_default_dockerfile(connector_path)
        
        tag = tag or f"{self.prefix}{connector_name}:latest"
        
        try:
            # Build image
            image, build_logs = self.client.images.build(
                path=str(connector_path),
                tag=tag,
                rm=True,  # Remove intermediate containers
                forcerm=True  # Always remove intermediate containers
            )
            
            # Log build output
            for log in build_logs:
                if 'stream' in log:
                    logger.info(log['stream'].strip())
            
            return True
            
        except Exception as e:
            logger.error(f"Error building image for {connector_name}: {e}")
            return False
    
    def create_or_update_container(self, connector_name: str, instance_id: str, 
                                   config: Dict[str, Any]) -> Optional[str]:
        """Create or update a container for an instance"""
        container_name = f"{self.prefix}{connector_name}_{instance_id}"
        
        # Check if container already exists
        existing = self.get_container(container_name)
        if existing:
            logger.info(f"Updating container {container_name}")
            # Stop and remove existing container
            try:
                existing.stop(timeout=10)
                existing.remove()
            except Exception as e:
                logger.error(f"Error removing existing container: {e}")
                return None
        
        # Create new container using existing method
        return self.create_container(connector_name, instance_id, config)
    
    def create_container(self, connector_name: str, instance_id: str, 
                        config: Dict[str, Any]) -> Optional[str]:
        """Create and start a container for an instance"""
        container_name = f"{self.prefix}{connector_name}_{instance_id}"
        
        # Check if container already exists
        existing = self.get_container(container_name)
        if existing:
            logger.warning(f"Container {container_name} already exists")
            return existing.short_id
        
        # Build image if needed
        image_tag = f"{self.prefix}{connector_name}:latest"
        try:
            self.client.images.get(image_tag)
        except docker.errors.ImageNotFound:
            logger.info(f"Building image for {connector_name}")
            if not self.build_image(connector_name, image_tag):
                return None
        
        # Prepare container configuration
        container_config = {
            "image": image_tag,
            "name": container_name,
            "detach": True,
            "restart_policy": {"Name": "unless-stopped"},
            "environment": [
                f"INSTANCE_NAME={instance_id}",
                "MODE=production",
                "PYTHONUNBUFFERED=1",
                f"IOT2MQTT_PATH=/app"
            ],
            "volumes": {
                str(self.host_base_path / "shared"): {"bind": "/app/shared", "mode": "ro"},
                str(self.host_base_path / "connectors" / connector_name / "instances"): {
                    "bind": "/app/instances",
                    "mode": "ro"
                },
                str(self.host_base_path / ".env"): {"bind": "/app/.env", "mode": "ro"}
            },
            "network_mode": "host",
            "labels": {
                "iot2mqtt.type": "connector",
                "iot2mqtt.connector": connector_name,
                "iot2mqtt.instance": instance_id
            }
        }
        
        # Add Docker socket if needed (for nested container management)
        if config.get("docker_access"):
            container_config["volumes"]["/var/run/docker.sock"] = {
                "bind": "/var/run/docker.sock",
                "mode": "rw"
            }
        
        try:
            # Create and start container
            container = self.client.containers.run(**container_config)
            logger.info(f"Created and started container {container_name}")
            return container.short_id
            
        except Exception as e:
            logger.error(f"Error creating container {container_name}: {e}")
            return None
    
    def update_docker_compose(self, connector_name: str, instance_id: str, 
                            config: Dict[str, Any]) -> bool:
        """Update docker-compose.yml with new service"""
        compose_file = self.base_path / "docker-compose.yml"
        
        # Load existing compose file
        if compose_file.exists():
            with open(compose_file) as f:
                compose_data = yaml.safe_load(f) or {}
        else:
            compose_data = {
                "version": "3.8",
                "services": {},
                "networks": {"iot2mqtt": {"driver": "bridge"}}
            }
        
        # Add service for instance
        service_name = f"{connector_name}_{instance_id}"
        compose_data["services"][service_name] = {
            "build": f"./connectors/{connector_name}",
            "container_name": f"{self.prefix}{service_name}",
            "restart": "unless-stopped",
            "volumes": [
                "./shared:/app/shared:ro",
                f"./connectors/{connector_name}/instances:/app/instances:ro"
            ],
            "environment": [
                f"INSTANCE_NAME={instance_id}",
                "MODE=production",
                "PYTHONUNBUFFERED=1"
            ],
            "env_file": [".env"],
            "networks": ["iot2mqtt"],
            "depends_on": []
        }
        
        # Add web service if not exists
        if "web" not in compose_data["services"]:
            compose_data["services"]["web"] = {
                "build": "./web",
                "container_name": f"{self.prefix}web",
                "ports": ["${WEB_PORT:-8765}:8765"],
                "volumes": [
                    "/var/run/docker.sock:/var/run/docker.sock",
                    "./connectors:/app/connectors",
                    "./secrets:/app/secrets",
                    "./.env:/app/.env"
                ],
                "environment": ["NODE_ENV=production"],
                "networks": ["iot2mqtt"],
                "restart": "unless-stopped",
                "labels": {"iot2mqtt.type": "web"}
            }
        
        # Save docker-compose.yml
        try:
            with open(compose_file, 'w') as f:
                yaml.dump(compose_data, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Updated docker-compose.yml with service {service_name}")
            return True
        except Exception as e:
            logger.error(f"Error updating docker-compose.yml: {e}")
            return False
    
    def _create_default_dockerfile(self, connector_path: Path):
        """Create default Dockerfile for connector"""
        dockerfile_content = """FROM python:3.11-slim

WORKDIR /app

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./

# Environment variables
ENV MODE=production
ENV PYTHONUNBUFFERED=1

# Run the connector
CMD ["python", "-u", "main.py"]
"""
        dockerfile = connector_path / "Dockerfile"
        dockerfile.write_text(dockerfile_content)
        logger.info(f"Created default Dockerfile for {connector_path.name}")
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get Docker system statistics"""
        stats = {
            "containers": {
                "total": 0,
                "running": 0,
                "stopped": 0
            },
            "images": 0,
            "volumes": 0
        }
        
        if not self.client:
            logger.warning("Docker client not connected")
            return stats
            
        try:
            # Count IoT2MQTT containers
            containers = self.list_containers()
            stats["containers"]["total"] = len(containers)
            stats["containers"]["running"] = sum(1 for c in containers if c.get("state") == "running")
            stats["containers"]["stopped"] = stats["containers"]["total"] - stats["containers"]["running"]
            
            # Count images
            for image in self.client.images.list():
                if any(tag.startswith(self.prefix) for tag in image.tags):
                    stats["images"] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}