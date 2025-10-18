"""
Configuration management service with file locking
"""

import os
import json
import yaml
import fcntl
import random
import string
from pathlib import Path
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
import shutil
from datetime import datetime
import logging
from .secrets_manager import SecretsManager

logger = logging.getLogger(__name__)


class ConfigService:
    """Service for managing configurations with file locking"""
    
    def __init__(self, base_path: str = None):
        raw_base_path = base_path or os.getenv("IOT2MQTT_PATH")
        if raw_base_path:
            candidate_base = Path(raw_base_path)
        else:
            candidate_base = self._detect_base_path()

        self.base_path = candidate_base.resolve()
        self.env_file = self.base_path / ".env"
        self.connectors_path = self.base_path / "connectors"
        self.instances_path = self.base_path / "instances"
        self.secrets_path = self.base_path / "secrets"
        self.discovered_devices_path = self.base_path / "discovered_devices.json"
        self.discovery_config_path = self.base_path / "discovery_config.json"
        self.frontend_dist_path = self._detect_frontend_dist_path()

        # Ensure core directories exist so API calls do not fail on clean installs
        self.connectors_path.mkdir(parents=True, exist_ok=True)
        self.instances_path.mkdir(parents=True, exist_ok=True)
        self.secrets_path.mkdir(parents=True, exist_ok=True)

        self.secrets_manager = SecretsManager(str(self.secrets_path))
    
    def _detect_base_path(self) -> Path:
        """Detect project base path when not explicitly provided"""
        candidate = Path(__file__).resolve()
        for parent in candidate.parents:
            # docker-compose.yml lives in repo root and inside container at /app
            if (parent / "docker-compose.yml").exists():
                return parent
        return Path.cwd()
    
    def _detect_frontend_dist_path(self) -> Path:
        """Locate built frontend assets directory"""
        candidates = [
            self.base_path / "frontend" / "dist",
            self.base_path / "web" / "frontend" / "dist",
            self.base_path / "frontend-dist"
        ]
        for candidate in candidates:
            if (candidate / "index.html").exists():
                return candidate
        # Fall back to first candidate even if it does not exist yet
        return candidates[0]
        
    @contextmanager
    def locked_file(self, filepath: Path, mode: str = 'r+'):
        """Context manager for file locking"""
        file = None
        try:
            # Ensure file exists for r+ mode
            if mode == 'r+' and not filepath.exists():
                filepath.touch()
                
            file = open(filepath, mode)
            fcntl.flock(file, fcntl.LOCK_EX)  # Exclusive lock
            yield file
        finally:
            if file:
                fcntl.flock(file, fcntl.LOCK_UN)  # Unlock
                file.close()
    
    @contextmanager
    def locked_json_file(self, filepath: Path):
        """Context manager for locked JSON file operations"""
        with self.locked_file(filepath, 'r+') as f:
            try:
                content = f.read()
                data = json.loads(content) if content else {}
            except json.JSONDecodeError:
                data = {}
            
            # Create a mutable container for the data
            container = {'data': data}
            yield container
            
            # Write back the data
            f.seek(0)
            json.dump(container['data'], f, indent=2)
            f.truncate()
    
    def load_env(self) -> Dict[str, str]:
        """Load environment variables from .env file"""
        env_vars = {}
        if self.env_file.exists():
            with self.locked_file(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
        return env_vars
    
    def save_env(self, env_vars: Dict[str, str], merge: bool = True):
        """Save environment variables to .env file"""
        if merge and self.env_file.exists():
            existing = self.load_env()
            existing.update(env_vars)
            env_vars = existing
        
        # Backup existing file
        if self.env_file.exists():
            backup = self.env_file.with_suffix(f'.env.{datetime.now().strftime("%Y%m%d_%H%M%S")}.bak')
            shutil.copy(self.env_file, backup)
        
        with self.locked_file(self.env_file, 'w') as f:
            f.write("# IoT2MQTT Configuration\n")
            f.write(f"# Generated at {datetime.now().isoformat()}\n\n")
            
            # Group related variables
            groups = {
                "Web Interface": ["WEB_ACCESS_KEY", "WEB_PORT"],
                "MQTT Broker Settings": ["MQTT_HOST", "MQTT_PORT", "MQTT_USERNAME", "MQTT_PASSWORD"],
                "MQTT Topics and Client": ["MQTT_BASE_TOPIC", "MQTT_CLIENT_PREFIX", "MQTT_QOS", "MQTT_RETAIN"],
                "Home Assistant Discovery": ["HA_DISCOVERY_ENABLED", "HA_DISCOVERY_PREFIX"],
                "Advanced Settings": ["MQTT_KEEPALIVE", "MQTT_CLEAN_SESSION", "RESPONSE_TIMEOUT", "MAX_RETRIES"]
            }
            
            written_keys = set()
            
            for group_name, keys in groups.items():
                group_has_values = any(k in env_vars for k in keys)
                if group_has_values:
                    f.write(f"# {group_name}\n")
                    for key in keys:
                        if key in env_vars:
                            f.write(f"{key}={env_vars[key]}\n")
                            written_keys.add(key)
                    f.write("\n")
            
            # Write any remaining variables
            remaining = {k: v for k, v in env_vars.items() if k not in written_keys}
            if remaining:
                f.write("# Other Settings\n")
                for key, value in remaining.items():
                    f.write(f"{key}={value}\n")
    
    def get_access_key(self) -> Optional[str]:
        """Get web access key from env"""
        env_vars = self.load_env()
        return env_vars.get("WEB_ACCESS_KEY")
    
    def set_access_key(self, key: str):
        """Set web access key"""
        self.save_env({"WEB_ACCESS_KEY": key})
    
    def get_mqtt_config(self) -> Dict[str, Any]:
        """Get MQTT configuration"""
        env_vars = self.load_env()
        return {
            "host": env_vars.get("MQTT_HOST", ""),
            "port": int(env_vars.get("MQTT_PORT", "1883")),
            "username": env_vars.get("MQTT_USERNAME", ""),
            "password": env_vars.get("MQTT_PASSWORD", ""),
            "base_topic": env_vars.get("MQTT_BASE_TOPIC", "IoT2mqtt"),
            "client_prefix": env_vars.get("MQTT_CLIENT_PREFIX", "iot2mqtt"),
            "qos": int(env_vars.get("MQTT_QOS", "1")),
            "retain": env_vars.get("MQTT_RETAIN", "true").lower() == "true",
            "keepalive": int(env_vars.get("MQTT_KEEPALIVE", "60"))
        }
    
    def save_mqtt_config(self, config: Dict[str, Any]):
        """Save MQTT configuration"""
        env_vars = {
            "MQTT_HOST": config["host"],
            "MQTT_PORT": str(config["port"]),
            "MQTT_USERNAME": config.get("username", ""),
            "MQTT_PASSWORD": config.get("password", ""),
            "MQTT_BASE_TOPIC": config.get("base_topic", "IoT2mqtt"),
            "MQTT_CLIENT_PREFIX": config.get("client_prefix", "iot2mqtt"),
            "MQTT_QOS": str(config.get("qos", 1)),
            "MQTT_RETAIN": str(config.get("retain", True)).lower(),
            "MQTT_KEEPALIVE": str(config.get("keepalive", 60))
        }
        self.save_env(env_vars)
    
    def list_connectors(self) -> List[Dict[str, Any]]:
        """List available connectors"""
        connectors = []
        
        if self.connectors_path.exists():
            for connector_dir in sorted(self.connectors_path.iterdir()):
                if not connector_dir.is_dir() or connector_dir.name.startswith('_'):
                    continue
                
                # Get connector info
                info = {
                    "name": connector_dir.name,
                    "display_name": connector_dir.name.replace('_', ' ').title(),
                    "instances": [],
                    "has_setup": (connector_dir / "setup.json").exists(),
                    "has_icon": (connector_dir / "icon.svg").exists()
                }
                
                # Count instances
                instance_dir = self.instances_path / connector_dir.name
                if instance_dir.exists():
                    info["instances"] = [f.stem for f in instance_dir.glob("*.json")]
                
                # Load setup.json if exists
                setup_json = connector_dir / "setup.json"
                if setup_json.exists():
                    with self.locked_file(setup_json, 'r') as f:
                        setup_data = json.load(f)
                        info["display_name"] = setup_data.get("display_name", info["display_name"])
                        info["description"] = setup_data.get("description", "")
                        info["version"] = setup_data.get("version", "1.0.0")
                
                connectors.append(info)
        
        return connectors
    
    def get_connector_setup(self, connector_name: str) -> Optional[Dict[str, Any]]:
        """Get connector setup schema"""
        setup_file = self.connectors_path / connector_name / "setup.json"
        
        if not setup_file.exists():
            return None

        with self.locked_file(setup_file, 'r') as f:
            return json.load(f)
    
    def list_instances(self, connector_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """List instances for a connector or all connectors"""
        instances = []
        
        if connector_name:
            # List instances for specific connector
            instances_dir = self.instances_path / connector_name
            if instances_dir.exists():
                for instance_file in instances_dir.glob("*.json"):
                    with self.locked_file(instance_file, 'r') as f:
                        data = json.load(f)
                        data["connector_type"] = connector_name
                        instances.append(data)
        else:
            # List all instances
            for connector_dir in self.connectors_path.iterdir():
                if connector_dir.is_dir() and not connector_dir.name.startswith('_'):
                    instances.extend(self.list_instances(connector_dir.name))
        
        return instances
    
    def get_instance_config(self, connector_name: str, instance_id: str) -> Optional[Dict[str, Any]]:
        """Get instance configuration"""
        instance_file = self.instances_path / connector_name / f"{instance_id}.json"
        
        if not instance_file.exists():
            return None
        
        with self.locked_file(instance_file, 'r') as f:
            return json.load(f)
    
    def save_instance_config(self, connector_name: str, instance_id: str, config: Dict[str, Any]):
        """Save instance configuration"""
        instances_dir = self.instances_path / connector_name
        instances_dir.mkdir(parents=True, exist_ok=True)

        instance_file = instances_dir / f"{instance_id}.json"
        
        # Add metadata
        config["instance_id"] = instance_id
        config["connector_type"] = connector_name
        config["updated_at"] = datetime.now().isoformat()
        
        if not instance_file.exists():
            config["created_at"] = datetime.now().isoformat()
        
        with self.locked_json_file(instance_file) as container:
            container['data'] = config
    
    def delete_instance_config(self, connector_name: str, instance_id: str) -> bool:
        """Delete instance configuration"""
        instance_file = self.instances_path / connector_name / f"{instance_id}.json"

        if instance_file.exists():
            # Backup before deletion
            backup_dir = self.instances_path / connector_name / ".backup"
            backup_dir.mkdir(exist_ok=True)
            backup_file = backup_dir / f"{instance_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            shutil.copy(instance_file, backup_file)
            
            instance_file.unlink()
            return True
        
        return False
    
    def load_docker_compose(self) -> Dict[str, Any]:
        """Load docker-compose.yml"""
        compose_file = self.base_path / "docker-compose.yml"
        
        if not compose_file.exists():
            return {"version": "3.8", "services": {}, "networks": {"iot2mqtt": {"driver": "bridge"}}}
        
        with self.locked_file(compose_file, 'r') as f:
            return yaml.safe_load(f) or {}
    
    def save_docker_compose(self, compose_data: Dict[str, Any]):
        """Save docker-compose.yml"""
        compose_file = self.base_path / "docker-compose.yml"
        
        # Backup existing file
        if compose_file.exists():
            backup = compose_file.with_suffix(f'.yml.{datetime.now().strftime("%Y%m%d_%H%M%S")}.bak')
            shutil.copy(compose_file, backup)
        
        with self.locked_file(compose_file, 'w') as f:
            yaml.dump(compose_data, f, default_flow_style=False, sort_keys=False)
    
    def save_instance_with_secrets(self, connector_name: str, instance_id: str,
                                  config: Dict[str, Any],
                                  explicit_secrets: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Save instance configuration with separated secrets"""
        # Extract sensitive fields
        clean_config, sensitive_data = self.secrets_manager.extract_sensitive_fields(config)

        if explicit_secrets:
            sensitive_data.update({k: v for k, v in explicit_secrets.items() if v is not None})
        
        # Save clean config
        self.save_instance_config(connector_name, instance_id, clean_config)

        # Save encrypted secrets if any
        if sensitive_data:
            self.secrets_manager.save_instance_secret(instance_id, sensitive_data)
        
        # Return Docker secret configuration
        return self.secrets_manager.create_docker_secret(instance_id, sensitive_data) if sensitive_data else {}
    
    def load_instance_with_secrets(self, connector_name: str, instance_id: str) -> Optional[Dict[str, Any]]:
        """Load instance configuration with injected secrets"""
        # Load clean config
        config = self.get_instance_config(connector_name, instance_id)
        if not config:
            return None
        
        # Load and inject secrets
        secrets = self.secrets_manager.load_instance_secret(instance_id)
        if secrets:
            config = self.secrets_manager.inject_secrets(config, secrets)
        
        return config
    
    def generate_unique_instance_id(self, connector_name: str, max_attempts: int = 10) -> str:
        """
        Generate a unique instance_id in format: {connector_name}_{random6}

        Args:
            connector_name: Name of the connector (e.g., "yeelight", "cameras")
            max_attempts: Maximum number of generation attempts

        Returns:
            Unique instance ID string

        Raises:
            RuntimeError: If unable to generate unique ID after max_attempts
        """
        for attempt in range(max_attempts):
            # Generate 6 random lowercase alphanumeric characters
            # Using same logic as frontend: Math.random().toString(36).substring(2, 8)
            random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            instance_id = f"{connector_name}_{random_suffix}"

            # Check if this ID already exists
            if not self.get_instance_config(connector_name, instance_id):
                logger.info(f"Generated unique instance_id: {instance_id} (attempt {attempt + 1})")
                return instance_id

            logger.debug(f"Instance ID {instance_id} already exists, retrying...")

        # Fallback: append timestamp to ensure uniqueness
        timestamp_suffix = datetime.now().strftime("%H%M%S")
        fallback_id = f"{connector_name}_{timestamp_suffix}"
        logger.warning(f"Could not generate random ID after {max_attempts} attempts, using timestamp: {fallback_id}")
        return fallback_id

    def get_connector_branding(self, connector_name: str) -> Dict[str, Any]:
        """Get connector branding information"""
        setup = self.get_connector_setup(connector_name)

        if setup and "branding" in setup:
            return setup["branding"]

        # Default branding
        connector_dir = self.connectors_path / connector_name
        return {
            "icon": f"/assets/brands/{connector_name}.svg" if (connector_dir / "icon.svg").exists() else "/assets/default-icon.svg",
            "color": "#6366F1",  # Default indigo
            "background": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            "category": "general"
        }
