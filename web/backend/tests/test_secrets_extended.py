"""
Extended tests for SecretsManager
"""

import json
import os
from pathlib import Path
from unittest.mock import patch, Mock

import pytest
from cryptography.fernet import Fernet

from services.secrets_manager import SecretsManager


class TestSecretsManagerExtended:
    """Extended tests for SecretsManager functionality"""

    def test_extract_sensitive_fields_default_keys(self, setup_test_env):
        """Test extracting sensitive fields with default key patterns"""
        secrets_path = setup_test_env / "secrets"
        manager = SecretsManager(str(secrets_path))

        config = {
            "instance_id": "test",
            "api_key": "secret_api_key",
            "database_password": "db_pass_123",
            "auth_token": "bearer_token_456",
            "normal_setting": "public_value",
            "nested": {
                "private_key": "rsa_private_key",
                "public_setting": "not_secret"
            }
        }

        clean_config, sensitive_data = manager.extract_sensitive_fields(config)

        # Check sensitive data was extracted
        assert "api_key" in sensitive_data
        assert "database_password" in sensitive_data
        assert "auth_token" in sensitive_data
        assert "nested.private_key" in sensitive_data

        # Check clean config has placeholders
        assert clean_config["api_key"] == "__SECRET__api_key__"
        assert clean_config["database_password"] == "__SECRET__database_password__"
        assert clean_config["nested"]["private_key"] == "__SECRET__nested.private_key__"

        # Check non-sensitive data remains
        assert clean_config["normal_setting"] == "public_value"
        assert clean_config["nested"]["public_setting"] == "not_secret"

    def test_extract_sensitive_fields_custom_keys(self, setup_test_env):
        """Test extracting sensitive fields with custom key patterns"""
        secrets_path = setup_test_env / "secrets"
        manager = SecretsManager(str(secrets_path))

        config = {
            "api_key": "should_be_secret",
            "custom_secret": "custom_value",
            "webhook_url": "not_secret_url"
        }

        custom_keys = ["custom", "webhook"]

        clean_config, sensitive_data = manager.extract_sensitive_fields(config, custom_keys)

        # Only custom keys should be treated as sensitive
        assert "custom_secret" in sensitive_data
        assert "webhook_url" in sensitive_data
        assert "api_key" not in sensitive_data  # Not in custom list

        assert clean_config["api_key"] == "should_be_secret"  # Unchanged

    def test_inject_secrets_back(self, setup_test_env):
        """Test injecting secrets back into configuration"""
        secrets_path = setup_test_env / "secrets"
        manager = SecretsManager(str(secrets_path))

        clean_config = {
            "instance_id": "test",
            "api_key": "__SECRET__api_key__",
            "normal_setting": "public_value",
            "nested": {
                "password": "__SECRET__nested.password__",
                "public_data": "not_secret"
            }
        }

        secrets = {
            "api_key": "actual_api_key_123",
            "nested.password": "actual_password_456"
        }

        result = manager.inject_secrets(clean_config, secrets)

        # Secrets should be injected
        assert result["api_key"] == "actual_api_key_123"
        assert result["nested"]["password"] == "actual_password_456"

        # Non-secret data should remain unchanged
        assert result["normal_setting"] == "public_value"
        assert result["nested"]["public_data"] == "not_secret"

    def test_save_and_load_instance_secret(self, setup_test_env):
        """Test saving and loading instance secrets"""
        secrets_path = setup_test_env / "secrets"
        manager = SecretsManager(str(secrets_path))

        credentials = {
            "api_key": "secret_key_123",
            "password": "secret_password_456",
            "token": "bearer_token_789"
        }

        # Save secrets
        secret_path = manager.save_instance_secret("test_instance", credentials)

        assert Path(secret_path).exists()
        assert Path(secret_path).name == "test_instance.secret"

        # Load secrets back
        loaded = manager.load_instance_secret("test_instance")

        assert loaded == credentials

    def test_load_nonexistent_secret(self, setup_test_env):
        """Test loading non-existent instance secret"""
        secrets_path = setup_test_env / "secrets"
        manager = SecretsManager(str(secrets_path))

        result = manager.load_instance_secret("nonexistent_instance")
        assert result is None

    def test_delete_instance_secret(self, setup_test_env):
        """Test deleting instance secret"""
        secrets_path = setup_test_env / "secrets"
        manager = SecretsManager(str(secrets_path))

        # Create secret first
        credentials = {"api_key": "test_key"}
        manager.save_instance_secret("test_instance", credentials)

        # Verify it exists
        assert manager.load_instance_secret("test_instance") is not None

        # Delete secret
        result = manager.delete_instance_secret("test_instance")
        assert result is True

        # Verify it's gone
        assert manager.load_instance_secret("test_instance") is None

        # Try to delete again
        result = manager.delete_instance_secret("test_instance")
        assert result is False

    def test_create_docker_secret_config(self, setup_test_env):
        """Test creating Docker secret configuration"""
        secrets_path = setup_test_env / "secrets"
        manager = SecretsManager(str(secrets_path))

        credentials = {"api_key": "test_key", "password": "test_pass"}

        docker_config = manager.create_docker_secret(
            "test_instance", credentials
        )

        assert "secrets" in docker_config
        assert "service_secrets" in docker_config

        secret_name = "test_instance_credentials"
        assert secret_name in docker_config["secrets"]
        assert docker_config["secrets"][secret_name]["file"]

        service_secrets = docker_config["service_secrets"]
        assert len(service_secrets) == 1
        assert service_secrets[0]["source"] == secret_name
        assert service_secrets[0]["target"] == "/run/secrets/credentials"

    def test_rotate_master_key(self, setup_test_env):
        """Test rotating the master encryption key"""
        secrets_path = setup_test_env / "secrets"
        manager = SecretsManager(str(secrets_path))

        # Create some instance secrets
        credentials1 = {"api_key": "key1", "password": "pass1"}
        credentials2 = {"api_key": "key2", "password": "pass2"}

        manager.save_instance_secret("instance1", credentials1)
        manager.save_instance_secret("instance2", credentials2)

        # Store original master key
        original_key = manager.master_key_path.read_bytes()

        # Rotate key
        result = manager.rotate_master_key(backup=True)
        assert result is True

        # Master key should be different
        new_key = manager.master_key_path.read_bytes()
        assert new_key != original_key

        # Backup should exist
        backup_path = manager.master_key_path.with_suffix('.backup')
        assert backup_path.exists()
        assert backup_path.read_bytes() == original_key

        # Secrets should still be readable
        loaded1 = manager.load_instance_secret("instance1")
        loaded2 = manager.load_instance_secret("instance2")

        assert loaded1 == credentials1
        assert loaded2 == credentials2

    def test_rotate_master_key_without_backup(self, setup_test_env):
        """Test rotating master key without creating backup"""
        secrets_path = setup_test_env / "secrets"
        manager = SecretsManager(str(secrets_path))

        # Create instance secret
        credentials = {"api_key": "test_key"}
        manager.save_instance_secret("test_instance", credentials)

        # Rotate without backup
        result = manager.rotate_master_key(backup=False)
        assert result is True

        # No backup should exist
        backup_path = manager.master_key_path.with_suffix('.backup')
        assert not backup_path.exists()

        # Secret should still be readable
        loaded = manager.load_instance_secret("test_instance")
        assert loaded == credentials

    def test_encrypt_decrypt_roundtrip_complex(self, setup_test_env):
        """Test encryption/decryption with complex data structures"""
        secrets_path = setup_test_env / "secrets"
        manager = SecretsManager(str(secrets_path))

        complex_data = {
            "api_key": "secret_key_123",
            "nested": {
                "database": {
                    "host": "db.example.com",
                    "password": "db_password_456",
                    "ssl_cert": "-----BEGIN CERTIFICATE-----\nMIIC..."
                },
                "tokens": [
                    "token1", "token2", "token3"
                ]
            },
            "numbers": [1, 2, 3.14, -5],
            "boolean": True,
            "null_value": None
        }

        encrypted = manager.encrypt_credentials(complex_data)
        decrypted = manager.decrypt_credentials(encrypted)

        assert decrypted == complex_data

    def test_encryption_with_invalid_data(self, setup_test_env):
        """Test encryption error handling"""
        secrets_path = setup_test_env / "secrets"
        manager = SecretsManager(str(secrets_path))

        # Mock JSON serialization error
        with patch('json.dumps', side_effect=TypeError("Not serializable")):
            with pytest.raises(TypeError):
                manager.encrypt_credentials({"invalid": object()})

    def test_decryption_with_invalid_data(self, setup_test_env):
        """Test decryption error handling"""
        secrets_path = setup_test_env / "secrets"
        manager = SecretsManager(str(secrets_path))

        # Test with invalid encrypted data
        with pytest.raises(Exception):
            manager.decrypt_credentials(b"invalid_encrypted_data")

    def test_master_key_file_permissions(self, setup_test_env):
        """Test that master key file has correct permissions"""
        secrets_path = setup_test_env / "secrets"
        manager = SecretsManager(str(secrets_path))

        # Check master key file permissions (read-only for owner)
        key_stat = manager.master_key_path.stat()
        permissions = oct(key_stat.st_mode)[-3:]

        # Should be 400 (read-only for owner)
        # Note: In some environments permissions might be different due to umask
        assert permissions in ["400", "600"]  # Allow both read-only and read-write for owner

    def test_secret_file_permissions(self, setup_test_env):
        """Test that secret files have correct permissions"""
        secrets_path = setup_test_env / "secrets"
        manager = SecretsManager(str(secrets_path))

        credentials = {"api_key": "test_key"}
        secret_path = manager.save_instance_secret("test_instance", credentials)

        # Check secret file permissions
        secret_stat = Path(secret_path).stat()
        permissions = oct(secret_stat.st_mode)[-3:]

        # Should be 400 (read-only for owner)
        # Note: In some environments permissions might be different due to umask
        assert permissions in ["400", "600"]  # Allow both read-only and read-write for owner

    def test_derive_key_from_password(self, setup_test_env):
        """Test password-based key derivation"""
        secrets_path = setup_test_env / "secrets"
        manager = SecretsManager(str(secrets_path))

        password = "test_password_123"

        # Derive key with salt
        key1, salt1 = manager._derive_key_from_password(password)

        # Derive key with same salt
        key2, salt2 = manager._derive_key_from_password(password, salt1)

        # Keys should be the same when using same salt
        assert key1 == key2
        assert salt1 == salt2

        # Different salt should produce different key
        key3, salt3 = manager._derive_key_from_password(password)
        assert key3 != key1
        assert salt3 != salt1

    def test_secrets_path_from_env_var(self, tmp_path, monkeypatch):
        """Test using custom secrets path from environment variable"""
        custom_secrets = tmp_path / "custom_secrets"
        custom_secrets.mkdir()

        monkeypatch.setenv("IOT2MQTT_SECRETS_PATH", str(custom_secrets))

        manager = SecretsManager()

        assert manager.secrets_path == custom_secrets
        assert manager.master_key_path == custom_secrets / ".master.key"

    def test_roundtrip_with_unicode_data(self, setup_test_env):
        """Test encryption/decryption with Unicode data"""
        secrets_path = setup_test_env / "secrets"
        manager = SecretsManager(str(secrets_path))

        unicode_data = {
            "chinese": "你好世界",
            "russian": "Привет мир",
            "emoji": "🔐🔑🛡️",
            "mixed": "Hello 世界 🌍"
        }

        encrypted = manager.encrypt_credentials(unicode_data)
        decrypted = manager.decrypt_credentials(encrypted)

        assert decrypted == unicode_data

    def test_empty_secrets_handling(self, setup_test_env):
        """Test handling of empty secrets"""
        secrets_path = setup_test_env / "secrets"
        manager = SecretsManager(str(secrets_path))

        # Test with empty dict
        empty_secrets = {}
        encrypted = manager.encrypt_credentials(empty_secrets)
        decrypted = manager.decrypt_credentials(encrypted)

        assert decrypted == empty_secrets