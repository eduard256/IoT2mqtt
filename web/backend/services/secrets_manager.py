"""
Secrets management service for secure credential storage
"""

import os
import json
import base64
from pathlib import Path
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)


class SecretsManager:
    """Manages encryption and storage of sensitive credentials"""
    
    def __init__(self, secrets_path: Optional[str] = None):
        raw_path = secrets_path or os.getenv("IOT2MQTT_SECRETS_PATH") or "/app/secrets"
        self.secrets_path = Path(raw_path)
        self.instances_path = self.secrets_path / "instances"
        self.master_key_path = self.secrets_path / ".master.key"
        
        # Create directories if they don't exist
        self.secrets_path.mkdir(parents=True, exist_ok=True)
        self.instances_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize encryption
        self.cipher = self._initialize_cipher()
    
    def _initialize_cipher(self) -> Fernet:
        """Initialize or load the master encryption key"""
        if self.master_key_path.exists():
            # Load existing key
            with open(self.master_key_path, 'rb') as f:
                key = f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            
            # Save with restricted permissions
            with open(self.master_key_path, 'wb') as f:
                f.write(key)
            os.chmod(self.master_key_path, 0o400)  # Read-only for owner
            
            logger.info("Generated new master encryption key")
        
        return Fernet(key)
    
    def _derive_key_from_password(self, password: str, salt: bytes = None) -> tuple[bytes, bytes]:
        """Derive encryption key from password using PBKDF2"""
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt
    
    def encrypt_credentials(self, credentials: Dict[str, Any]) -> bytes:
        """Encrypt credentials dictionary"""
        try:
            # Convert to JSON
            json_str = json.dumps(credentials, separators=(',', ':'))
            
            # Encrypt
            encrypted = self.cipher.encrypt(json_str.encode())
            
            return encrypted
        except Exception as e:
            logger.error(f"Failed to encrypt credentials: {e}")
            raise
    
    def decrypt_credentials(self, encrypted_data: bytes) -> Dict[str, Any]:
        """Decrypt credentials"""
        try:
            # Decrypt
            decrypted = self.cipher.decrypt(encrypted_data)
            
            # Parse JSON
            credentials = json.loads(decrypted.decode())
            
            return credentials
        except Exception as e:
            logger.error(f"Failed to decrypt credentials: {e}")
            raise
    
    def save_instance_secret(self, instance_id: str, credentials: Dict[str, Any]) -> str:
        """Save encrypted credentials for an instance"""
        try:
            # Encrypt credentials
            encrypted = self.encrypt_credentials(credentials)
            
            # Save to file
            secret_path = self.instances_path / f"{instance_id}.secret"
            with open(secret_path, 'wb') as f:
                f.write(encrypted)
            
            # Set restrictive permissions
            os.chmod(secret_path, 0o400)
            
            logger.info(f"Saved encrypted credentials for instance: {instance_id}")
            return str(secret_path)
            
        except Exception as e:
            logger.error(f"Failed to save instance secret: {e}")
            raise
    
    def load_instance_secret(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """Load and decrypt instance credentials"""
        secret_path = self.instances_path / f"{instance_id}.secret"
        
        if not secret_path.exists():
            logger.warning(f"Secret file not found for instance: {instance_id}")
            return None
        
        try:
            # Read encrypted data
            with open(secret_path, 'rb') as f:
                encrypted = f.read()
            
            # Decrypt
            credentials = self.decrypt_credentials(encrypted)
            
            return credentials
            
        except Exception as e:
            logger.error(f"Failed to load instance secret: {e}")
            return None
    
    def delete_instance_secret(self, instance_id: str) -> bool:
        """Delete instance secret file"""
        secret_path = self.instances_path / f"{instance_id}.secret"
        
        if secret_path.exists():
            try:
                secret_path.unlink()
                logger.info(f"Deleted secret for instance: {instance_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete instance secret: {e}")
                return False
        
        return False
    
    def extract_sensitive_fields(self, config: Dict[str, Any], 
                                 sensitive_keys: list = None) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Extract sensitive fields from configuration
        
        Returns:
            (clean_config, sensitive_data)
        """
        if sensitive_keys is None:
            # Default sensitive field names
            sensitive_keys = [
                'password', 'token', 'api_key', 'secret', 
                'private_key', 'credential', 'auth_token'
            ]
        
        sensitive_data = {}
        clean_config = config.copy()
        
        def extract_recursive(data: dict, path: str = ""):
            """Recursively extract sensitive fields"""
            for key, value in list(data.items()):
                current_path = f"{path}.{key}" if path else key
                
                # Check if key is sensitive
                if any(s in key.lower() for s in sensitive_keys):
                    sensitive_data[current_path] = value
                    data[key] = f"__SECRET__{current_path}__"
                
                # Recurse into nested dicts
                elif isinstance(value, dict):
                    extract_recursive(value, current_path)
        
        extract_recursive(clean_config)
        
        return clean_config, sensitive_data
    
    def inject_secrets(self, config: Dict[str, Any], secrets: Dict[str, Any]) -> Dict[str, Any]:
        """Inject secrets back into configuration"""
        result = config.copy()
        
        def inject_recursive(data: dict):
            """Recursively inject secrets"""
            for key, value in data.items():
                if isinstance(value, str) and value.startswith("__SECRET__"):
                    # Extract secret path
                    secret_path = value.replace("__SECRET__", "").replace("__", "")
                    if secret_path in secrets:
                        data[key] = secrets[secret_path]
                elif isinstance(value, dict):
                    inject_recursive(value)
        
        inject_recursive(result)
        return result
    
    def create_docker_secret(self, instance_id: str, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create Docker secret configuration for docker-compose
        
        Returns Docker secret configuration dict
        """
        # Save encrypted secret
        secret_path = self.save_instance_secret(instance_id, credentials)
        
        # Return Docker secret config
        return {
            "secrets": {
                f"{instance_id}_credentials": {
                    "file": secret_path
                }
            },
            "service_secrets": [
                {
                    "source": f"{instance_id}_credentials",
                    "target": "/run/secrets/credentials",
                    "mode": 0o400
                }
            ]
        }
    
    def rotate_master_key(self, backup: bool = True) -> bool:
        """Rotate the master encryption key"""
        try:
            # Backup current key if requested
            if backup and self.master_key_path.exists():
                backup_path = self.master_key_path.with_suffix('.backup')
                with open(self.master_key_path, 'rb') as f:
                    old_key = f.read()
                with open(backup_path, 'wb') as f:
                    f.write(old_key)
                os.chmod(backup_path, 0o400)
            
            # Load all existing secrets
            all_secrets = {}
            for secret_file in self.instances_path.glob("*.secret"):
                instance_id = secret_file.stem
                credentials = self.load_instance_secret(instance_id)
                if credentials:
                    all_secrets[instance_id] = credentials
            
            # Generate new key
            new_key = Fernet.generate_key()
            with open(self.master_key_path, 'wb') as f:
                f.write(new_key)
            os.chmod(self.master_key_path, 0o400)
            
            # Re-initialize cipher with new key
            self.cipher = Fernet(new_key)
            
            # Re-encrypt all secrets with new key
            for instance_id, credentials in all_secrets.items():
                self.save_instance_secret(instance_id, credentials)
            
            logger.info("Successfully rotated master encryption key")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rotate master key: {e}")
            return False
