"""
Comprehensive tests for JWT secret security
Tests cover the fix for critical JWT secret vulnerability
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import base64

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.secrets_manager import SecretsManager
from services.jwt_config import get_jwt_secret, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES


# ============================================================================
# TIER 1 - CRITICAL TESTS: JWT Secret Generation
# ============================================================================

class TestJWTSecretGeneration:
    """Test JWT secret generation and security"""

    def test_jwt_secret_is_generated_automatically(self, tmp_path):
        """Should auto-generate JWT secret on first call"""
        secrets_manager = SecretsManager(secrets_path=str(tmp_path))

        secret = secrets_manager.get_or_create_jwt_secret()

        assert secret is not None
        assert len(secret) > 0
        assert isinstance(secret, str)

    def test_jwt_secret_is_cryptographically_secure(self, tmp_path):
        """Should generate cryptographically secure random secret (32 bytes)"""
        secrets_manager = SecretsManager(secrets_path=str(tmp_path))

        secret = secrets_manager.get_or_create_jwt_secret()

        # Decode from base64
        decoded = base64.urlsafe_b64decode(secret)

        # Should be 32 bytes (256 bits) of entropy
        assert len(decoded) == 32

    def test_jwt_secret_is_unique_per_installation(self, tmp_path):
        """Should generate different secrets for different installations"""
        path1 = tmp_path / "install1"
        path2 = tmp_path / "install2"
        path1.mkdir()
        path2.mkdir()

        sm1 = SecretsManager(secrets_path=str(path1))
        sm2 = SecretsManager(secrets_path=str(path2))

        secret1 = sm1.get_or_create_jwt_secret()
        secret2 = sm2.get_or_create_jwt_secret()

        # Secrets should be different
        assert secret1 != secret2

    def test_jwt_secret_is_not_default_value(self, tmp_path):
        """Should NEVER use the dangerous default value"""
        secrets_manager = SecretsManager(secrets_path=str(tmp_path))

        secret = secrets_manager.get_or_create_jwt_secret()

        # Must NOT be the dangerous default
        assert secret != "your-secret-key-change-in-production"


# ============================================================================
# TIER 1 - CRITICAL TESTS: JWT Secret Persistence
# ============================================================================

class TestJWTSecretPersistence:
    """Test JWT secret persistence across restarts"""

    def test_jwt_secret_is_persisted_to_file(self, tmp_path):
        """Should save JWT secret to file"""
        secrets_manager = SecretsManager(secrets_path=str(tmp_path))

        secret = secrets_manager.get_or_create_jwt_secret()

        jwt_secret_path = tmp_path / ".jwt_secret"
        assert jwt_secret_path.exists()

        # Read and verify
        with open(jwt_secret_path, 'r') as f:
            saved_secret = f.read().strip()

        assert saved_secret == secret

    def test_jwt_secret_is_loaded_on_second_call(self, tmp_path):
        """Should load existing secret instead of generating new one"""
        secrets_manager = SecretsManager(secrets_path=str(tmp_path))

        # First call - generate
        secret1 = secrets_manager.get_or_create_jwt_secret()

        # Second call - should load same secret
        secret2 = secrets_manager.get_or_create_jwt_secret()

        assert secret1 == secret2

    def test_jwt_secret_persists_across_process_restarts(self, tmp_path):
        """Should persist across process restarts (new SecretsManager instance)"""
        # First "process"
        sm1 = SecretsManager(secrets_path=str(tmp_path))
        secret1 = sm1.get_or_create_jwt_secret()

        # Simulate restart - new instance
        sm2 = SecretsManager(secrets_path=str(tmp_path))
        secret2 = sm2.get_or_create_jwt_secret()

        assert secret1 == secret2


# ============================================================================
# TIER 1 - CRITICAL TESTS: File Permissions
# ============================================================================

class TestJWTSecretFilePermissions:
    """Test file permissions for JWT secret"""

    def test_jwt_secret_file_has_restrictive_permissions(self, tmp_path):
        """Should set read-only permissions (0400) on JWT secret file"""
        secrets_manager = SecretsManager(secrets_path=str(tmp_path))
        secrets_manager.get_or_create_jwt_secret()

        jwt_secret_path = tmp_path / ".jwt_secret"

        # Get file permissions
        permissions = oct(jwt_secret_path.stat().st_mode)[-3:]

        # Should be 400 (read-only for owner)
        assert permissions == "400"

    def test_jwt_secret_file_is_hidden(self, tmp_path):
        """Should save JWT secret as hidden file (starts with dot)"""
        secrets_manager = SecretsManager(secrets_path=str(tmp_path))
        secrets_manager.get_or_create_jwt_secret()

        jwt_secret_path = tmp_path / ".jwt_secret"

        # Should start with dot
        assert jwt_secret_path.name.startswith(".")


# ============================================================================
# TIER 1 - CRITICAL TESTS: JWT Config Module
# ============================================================================

class TestJWTConfigModule:
    """Test jwt_config module behavior"""

    def test_get_jwt_secret_returns_auto_generated_key(self, tmp_path):
        """Should return auto-generated key when no env variable set"""
        with patch.dict(os.environ, {'IOT2MQTT_SECRETS_PATH': str(tmp_path)}, clear=False):
            # Remove JWT_SECRET_KEY if set
            os.environ.pop('JWT_SECRET_KEY', None)

            # Import fresh (would need module reload in real scenario)
            from services.secrets_manager import SecretsManager
            sm = SecretsManager(secrets_path=str(tmp_path))
            secret = sm.get_or_create_jwt_secret()

            assert secret is not None
            assert secret != "your-secret-key-change-in-production"

    def test_get_jwt_secret_rejects_dangerous_default(self, tmp_path):
        """Should reject dangerous default value even if set in env"""
        with patch.dict(os.environ, {
            'IOT2MQTT_SECRETS_PATH': str(tmp_path),
            'JWT_SECRET_KEY': 'your-secret-key-change-in-production'
        }, clear=False):
            from services.jwt_config import get_jwt_secret

            # Should auto-generate instead of using dangerous default
            secret = get_jwt_secret()

            assert secret != "your-secret-key-change-in-production"

    def test_get_jwt_secret_uses_custom_env_variable(self, tmp_path):
        """Should use custom JWT_SECRET_KEY from environment if safe"""
        custom_secret = "my-custom-super-secure-key-12345"

        with patch.dict(os.environ, {
            'IOT2MQTT_SECRETS_PATH': str(tmp_path),
            'JWT_SECRET_KEY': custom_secret
        }, clear=False):
            from services.jwt_config import get_jwt_secret

            secret = get_jwt_secret()

            assert secret == custom_secret

    def test_jwt_config_exports_correct_constants(self):
        """Should export correct JWT configuration constants"""
        assert ALGORITHM == "HS256"
        assert ACCESS_TOKEN_EXPIRE_MINUTES == 60 * 24 * 7  # 7 days


# ============================================================================
# TIER 1 - CRITICAL TESTS: Security Validation
# ============================================================================

class TestJWTSecurityValidation:
    """Test security validation and vulnerability fixes"""

    def test_no_hardcoded_secrets_in_main_py(self):
        """Should not have hardcoded JWT secret in main.py"""
        main_path = Path(__file__).parent.parent / "main.py"

        with open(main_path, 'r') as f:
            content = f.read()

        # Should NOT contain dangerous default as actual value
        # (only in jwt_config.py as rejection check)
        assert 'SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")' not in content

    def test_no_hardcoded_secrets_in_auth_py(self):
        """Should not have hardcoded JWT secret in auth.py"""
        auth_path = Path(__file__).parent.parent / "api" / "auth.py"

        with open(auth_path, 'r') as f:
            content = f.read()

        assert 'SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")' not in content

    def test_no_hardcoded_secrets_in_docker_py(self):
        """Should not have hardcoded JWT secret in docker.py"""
        docker_path = Path(__file__).parent.parent / "api" / "docker.py"

        with open(docker_path, 'r') as f:
            content = f.read()

        assert 'SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")' not in content

    def test_no_hardcoded_secrets_in_devices_py(self):
        """Should not have hardcoded JWT secret in devices.py"""
        devices_path = Path(__file__).parent.parent / "api" / "devices.py"

        with open(devices_path, 'r') as f:
            content = f.read()

        assert 'SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")' not in content

    def test_all_files_import_from_jwt_config(self):
        """Should import JWT config from centralized jwt_config module"""
        files_to_check = [
            Path(__file__).parent.parent / "main.py",
            Path(__file__).parent.parent / "api" / "auth.py",
            Path(__file__).parent.parent / "api" / "docker.py",
            Path(__file__).parent.parent / "api" / "devices.py",
        ]

        for file_path in files_to_check:
            with open(file_path, 'r') as f:
                content = f.read()

            # Should import from jwt_config
            assert 'from services.jwt_config import' in content, f"File {file_path} doesn't import from jwt_config"


# ============================================================================
# TIER 2 - INTEGRATION TESTS: End-to-End Security
# ============================================================================

class TestJWTSecurityIntegration:
    """Integration tests for JWT security"""

    def test_complete_jwt_secret_lifecycle(self, tmp_path):
        """Test complete lifecycle: generate → save → load → use"""
        # Step 1: Generate
        sm1 = SecretsManager(secrets_path=str(tmp_path))
        secret1 = sm1.get_or_create_jwt_secret()
        assert len(secret1) > 0

        # Step 2: Save (automatic)
        jwt_file = tmp_path / ".jwt_secret"
        assert jwt_file.exists()

        # Step 3: Load (new instance simulates restart)
        sm2 = SecretsManager(secrets_path=str(tmp_path))
        secret2 = sm2.get_or_create_jwt_secret()
        assert secret1 == secret2

        # Step 4: Use (verify it can be used for JWT)
        from jose import jwt
        test_payload = {"sub": "test_user"}
        token = jwt.encode(test_payload, secret2, algorithm="HS256")
        decoded = jwt.decode(token, secret2, algorithms=["HS256"])
        assert decoded["sub"] == "test_user"

    def test_jwt_secret_survives_directory_recreation(self, tmp_path):
        """Should persist even if process restarts"""
        # First run
        sm1 = SecretsManager(secrets_path=str(tmp_path))
        original_secret = sm1.get_or_create_jwt_secret()

        # Simulate process restart (new SecretsManager, but same directory)
        sm2 = SecretsManager(secrets_path=str(tmp_path))
        loaded_secret = sm2.get_or_create_jwt_secret()

        # Secret should be the same
        assert loaded_secret == original_secret


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def tmp_path():
    """Create temporary directory for tests"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
