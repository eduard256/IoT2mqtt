"""
Tests for authentication API endpoints
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from jose import jwt

from api.auth import (
    create_access_token,
    verify_token,
    verify_password,
    get_password_hash,
    SECRET_KEY,
    ALGORITHM
)


class TestAuthentication:
    """Test authentication functions"""

    def test_password_hashing(self):
        """Test password hashing and verification"""
        password = "test_password_123"
        hashed = get_password_hash(password)

        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("wrong_password", hashed) is False

    def test_create_access_token(self):
        """Test JWT token creation"""
        data = {"sub": "testuser"}
        token = create_access_token(data)

        # Decode token to verify content
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert "exp" in payload

    def test_create_access_token_with_expiry(self):
        """Test JWT token creation with custom expiry"""
        data = {"sub": "testuser"}
        expires_delta = timedelta(hours=1)
        token = create_access_token(data, expires_delta)

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"

        # Check expiry is approximately 1 hour from now
        exp_time = datetime.fromtimestamp(payload["exp"])
        expected_time = datetime.now(timezone.utc).replace(tzinfo=None) + expires_delta
        assert abs((exp_time - expected_time).total_seconds()) < 60  # Within 1 minute

    def test_verify_valid_token(self):
        """Test verification of valid token"""
        data = {"sub": "testuser"}
        token = create_access_token(data)

        # Mock credentials
        mock_credentials = Mock()
        mock_credentials.credentials = token

        result = verify_token(mock_credentials)
        assert result["username"] == "testuser"

    def test_verify_invalid_token(self):
        """Test verification of invalid token"""
        mock_credentials = Mock()
        mock_credentials.credentials = "invalid_token"

        with pytest.raises(HTTPException) as exc_info:
            verify_token(mock_credentials)

        assert exc_info.value.status_code == 403

    def test_verify_expired_token(self):
        """Test verification of expired token"""
        data = {"sub": "testuser"}
        # Create token that expires immediately
        expires_delta = timedelta(seconds=-1)
        token = create_access_token(data, expires_delta)

        mock_credentials = Mock()
        mock_credentials.credentials = token

        with pytest.raises(HTTPException) as exc_info:
            verify_token(mock_credentials)

        assert exc_info.value.status_code == 403


class TestAuthAPI:
    """Test authentication API endpoints"""

    @pytest.fixture
    def mock_config_service(self, setup_test_env):
        """Mock ConfigService for testing"""
        with patch('api.auth.ConfigService') as mock:
            service = mock.return_value
            yield service

    def test_login_first_time_setup(self, setup_test_env):
        """Test login when no access key is set (first time setup)"""
        with patch('services.config_service.ConfigService') as mock_cs:
            service_instance = mock_cs.return_value
            service_instance.get_access_key.return_value = None

            from api.auth import login
            import asyncio
            result = asyncio.run(login("new_password"))

            # Should set the access key
            service_instance.set_access_key.assert_called_once()

            # Should return valid token
            assert "access_token" in result
            assert result["token_type"] == "bearer"
            assert isinstance(result["expires_in"], int)

    def test_login_correct_password(self, setup_test_env):
        """Test login with correct password"""
        with patch('services.config_service.ConfigService') as mock_cs:
            service_instance = mock_cs.return_value
            password = "test_password"
            hashed = get_password_hash(password)
            service_instance.get_access_key.return_value = hashed

            from api.auth import login
            import asyncio
            result = asyncio.run(login(password))

            # Should not set access key again
            service_instance.set_access_key.assert_not_called()

            # Should return valid token
            assert "access_token" in result
            assert result["token_type"] == "bearer"

    def test_login_wrong_password(self, setup_test_env):
        """Test login with wrong password"""
        with patch('services.config_service.ConfigService') as mock_cs:
            service_instance = mock_cs.return_value
            password = "correct_password"
            hashed = get_password_hash(password)
            service_instance.get_access_key.return_value = hashed

            from api.auth import login
            import asyncio
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(login("wrong_password"))

            assert exc_info.value.status_code == 401
            assert "Invalid access key" in str(exc_info.value.detail)

    def test_verify_endpoint(self):
        """Test verify endpoint"""
        from api.auth import verify

        mock_token_data = {"username": "testuser"}

        import asyncio
        result = asyncio.run(verify(mock_token_data))

        assert result["valid"] is True
        assert result["user"] == "testuser"