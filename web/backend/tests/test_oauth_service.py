"""
Comprehensive tests for OAuthService

Tests cover:
1. Service initialization and directory creation
2. Provider configuration loading
3. OAuth session creation (session_id, state, authorization_url)
4. Session completion (token exchange)
5. Session retrieval and state lookup
6. File-based session storage
7. HTTP requests to token endpoint (mocked)
8. Error handling (missing provider, missing redirect_uri, HTTP errors)
9. Edge cases (malformed JSON, missing files, invalid state)
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.oauth_service import OAuthService, get_oauth_service


# ============================================================================
# TIER 1 - CRITICAL TESTS: Service Initialization
# ============================================================================

class TestServiceInitialization:
    """Test OAuthService initialization and directory setup"""

    def test_initialization_with_custom_path(self):
        """Should initialize with custom base path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            assert service.base_path == Path(tmpdir).resolve()
            assert service.config_path == Path(tmpdir) / "config" / "oauth"
            assert service.sessions_path == Path(tmpdir) / "oauth_sessions"

    def test_initialization_creates_directories(self):
        """Should create config and sessions directories"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            assert service.config_path.exists()
            assert service.config_path.is_dir()
            assert service.sessions_path.exists()
            assert service.sessions_path.is_dir()

    def test_initialization_without_path_uses_env(self):
        """Should use IOT2MQTT_PATH from environment if no path provided"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict('os.environ', {'IOT2MQTT_PATH': tmpdir}):
                service = OAuthService()

                assert str(service.base_path) == str(Path(tmpdir).resolve())

    def test_initialization_without_path_falls_back_to_default(self):
        """Should fall back to parent directory if no env and no path"""
        with patch.dict('os.environ', {}, clear=True):
            service = OAuthService()

            # Should use 2 levels up from oauth_service.py file
            assert service.base_path is not None
            assert service.base_path.exists()


# ============================================================================
# TIER 1 - CRITICAL TESTS: Provider Configuration Loading
# ============================================================================

class TestProviderLoading:
    """Test loading OAuth provider configurations"""

    def test_load_provider_success(self):
        """Should load provider configuration from JSON file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            # Create provider config
            provider_config = {
                "client_id": "test_client_id",
                "client_secret": "test_secret",
                "authorization_endpoint": "https://provider.com/oauth/authorize",
                "token_endpoint": "https://provider.com/oauth/token",
                "scopes": ["read", "write"]
            }
            config_file = service.config_path / "google.json"
            config_file.write_text(json.dumps(provider_config))

            # Load provider
            loaded = service.load_provider("google")

            assert loaded["client_id"] == "test_client_id"
            assert loaded["authorization_endpoint"] == "https://provider.com/oauth/authorize"
            assert loaded["scopes"] == ["read", "write"]

    def test_load_provider_not_found(self):
        """Should raise FileNotFoundError for missing provider"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            with pytest.raises(FileNotFoundError, match="OAuth provider 'nonexistent' is not configured"):
                service.load_provider("nonexistent")

    def test_load_provider_malformed_json(self):
        """Should raise JSONDecodeError for malformed JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            # Create malformed config
            config_file = service.config_path / "broken.json"
            config_file.write_text("{ invalid json")

            with pytest.raises(json.JSONDecodeError):
                service.load_provider("broken")


# ============================================================================
# TIER 1 - CRITICAL TESTS: Session Creation
# ============================================================================

class TestSessionCreation:
    """Test OAuth session creation"""

    def test_create_session_success(self):
        """Should create OAuth session and return authorization URL"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            # Create provider config
            provider_config = {
                "client_id": "test_client",
                "authorization_endpoint": "https://provider.com/auth",
                "token_endpoint": "https://provider.com/token",
                "redirect_uri": "http://localhost:8765/callback",
                "scopes": ["openid", "profile"],
                "scope_separator": " "
            }
            (service.config_path / "google.json").write_text(json.dumps(provider_config))

            # Create session
            result = service.create_session("google")

            # Should return session metadata
            assert "session_id" in result
            assert "state" in result
            assert "authorization_url" in result

            # Session ID should be valid UUID hex
            assert len(result["session_id"]) == 32
            assert len(result["state"]) == 32

            # Authorization URL should contain parameters
            auth_url = result["authorization_url"]
            assert "https://provider.com/auth?" in auth_url
            assert "client_id=test_client" in auth_url
            assert f"state={result['state']}" in auth_url
            assert "redirect_uri=http%3A%2F%2Flocalhost%3A8765%2Fcallback" in auth_url
            assert "scope=openid+profile" in auth_url

    def test_create_session_with_custom_redirect_uri(self):
        """Should use custom redirect_uri over provider config"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            provider_config = {
                "client_id": "test_client",
                "authorization_endpoint": "https://provider.com/auth",
                "token_endpoint": "https://provider.com/token",
                "redirect_uri": "http://default.com/callback"
            }
            (service.config_path / "google.json").write_text(json.dumps(provider_config))

            # Create session with custom redirect
            result = service.create_session("google", redirect_uri="http://custom.com/callback")

            # Should use custom redirect_uri
            assert "redirect_uri=http%3A%2F%2Fcustom.com%2Fcallback" in result["authorization_url"]

    def test_create_session_no_redirect_uri(self):
        """Should raise ValueError if no redirect_uri provided"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            provider_config = {
                "client_id": "test_client",
                "authorization_endpoint": "https://provider.com/auth",
                "token_endpoint": "https://provider.com/token"
                # No redirect_uri
            }
            (service.config_path / "google.json").write_text(json.dumps(provider_config))

            with pytest.raises(ValueError, match="Redirect URI must be specified"):
                service.create_session("google")

    def test_create_session_stores_session_file(self):
        """Should store session metadata in JSON file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            provider_config = {
                "client_id": "test_client",
                "authorization_endpoint": "https://provider.com/auth",
                "token_endpoint": "https://provider.com/token",
                "redirect_uri": "http://localhost/callback"
            }
            (service.config_path / "google.json").write_text(json.dumps(provider_config))

            result = service.create_session("google")

            # Session file should exist
            session_file = service.sessions_path / f"{result['session_id']}.json"
            assert session_file.exists()

            # Check session content
            session_data = json.loads(session_file.read_text())
            assert session_data["id"] == result["session_id"]
            assert session_data["provider"] == "google"
            assert session_data["state"] == result["state"]
            assert session_data["status"] == "pending"
            assert session_data["tokens"] is None
            assert "issued_at" in session_data

    def test_create_session_with_scopes(self):
        """Should include scopes in authorization URL"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            provider_config = {
                "client_id": "test_client",
                "authorization_endpoint": "https://provider.com/auth",
                "token_endpoint": "https://provider.com/token",
                "redirect_uri": "http://localhost/callback",
                "scopes": ["read:user", "read:org"],
                "scope_separator": " "
            }
            (service.config_path / "google.json").write_text(json.dumps(provider_config))

            result = service.create_session("google")

            assert "scope=read%3Auser+read%3Aorg" in result["authorization_url"]

    def test_create_session_with_extra_params(self):
        """Should include extra_authorize_params in URL"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            provider_config = {
                "client_id": "test_client",
                "authorization_endpoint": "https://provider.com/auth",
                "token_endpoint": "https://provider.com/token",
                "redirect_uri": "http://localhost/callback",
                "extra_authorize_params": {
                    "access_type": "offline",
                    "prompt": "consent"
                }
            }
            (service.config_path / "google.json").write_text(json.dumps(provider_config))

            result = service.create_session("google")

            assert "access_type=offline" in result["authorization_url"]
            assert "prompt=consent" in result["authorization_url"]


# ============================================================================
# TIER 1 - CRITICAL TESTS: Session Completion (Token Exchange)
# ============================================================================

class TestSessionCompletion:
    """Test OAuth session completion and token exchange"""

    def test_complete_session_success(self):
        """Should exchange authorization code for tokens"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            # Setup provider
            provider_config = {
                "client_id": "test_client",
                "client_secret": "test_secret",
                "authorization_endpoint": "https://provider.com/auth",
                "token_endpoint": "https://provider.com/token",
                "redirect_uri": "http://localhost/callback"
            }
            (service.config_path / "google.json").write_text(json.dumps(provider_config))

            # Create session
            session_result = service.create_session("google")
            state = session_result["state"]

            # Mock HTTP response for token exchange
            mock_response = Mock()
            mock_response.json.return_value = {
                "access_token": "access_token_abc123",
                "refresh_token": "refresh_token_xyz789",
                "expires_in": 3600,
                "token_type": "Bearer"
            }
            mock_response.raise_for_status = Mock()

            with patch('requests.post', return_value=mock_response) as mock_post:
                result = service.complete_session("google", state, code="auth_code_123")

                # Should call token endpoint
                mock_post.assert_called_once()
                call_args = mock_post.call_args
                assert call_args[0][0] == "https://provider.com/token"
                assert call_args[1]["data"]["grant_type"] == "authorization_code"
                assert call_args[1]["data"]["code"] == "auth_code_123"
                assert call_args[1]["data"]["client_id"] == "test_client"
                assert call_args[1]["data"]["client_secret"] == "test_secret"

                # Should return tokens
                assert result["session_id"] == session_result["session_id"]
                assert result["tokens"]["access_token"] == "access_token_abc123"

            # Session should be updated
            session_data = service.get_session(session_result["session_id"])
            assert session_data["status"] == "authorized"
            assert session_data["tokens"]["access_token"] == "access_token_abc123"

    def test_complete_session_invalid_state(self):
        """Should raise LookupError for unknown state"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            provider_config = {
                "client_id": "test_client",
                "authorization_endpoint": "https://provider.com/auth",
                "token_endpoint": "https://provider.com/token",
                "redirect_uri": "http://localhost/callback"
            }
            (service.config_path / "google.json").write_text(json.dumps(provider_config))

            with pytest.raises(LookupError, match="Unknown or mismatched OAuth session"):
                service.complete_session("google", state="invalid_state", code="code123")

    def test_complete_session_provider_mismatch(self):
        """Should raise LookupError if provider doesn't match"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            # Setup two providers
            for provider in ["google", "github"]:
                provider_config = {
                    "client_id": f"{provider}_client",
                    "authorization_endpoint": f"https://{provider}.com/auth",
                    "token_endpoint": f"https://{provider}.com/token",
                    "redirect_uri": "http://localhost/callback"
                }
                (service.config_path / f"{provider}.json").write_text(json.dumps(provider_config))

            # Create session for google
            session_result = service.create_session("google")
            state = session_result["state"]

            # Try to complete with github (mismatch)
            with pytest.raises(LookupError, match="Unknown or mismatched OAuth session"):
                service.complete_session("github", state=state, code="code123")

    def test_complete_session_http_error(self):
        """Should propagate HTTP errors from token endpoint"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            provider_config = {
                "client_id": "test_client",
                "authorization_endpoint": "https://provider.com/auth",
                "token_endpoint": "https://provider.com/token",
                "redirect_uri": "http://localhost/callback"
            }
            (service.config_path / "google.json").write_text(json.dumps(provider_config))

            session_result = service.create_session("google")
            state = session_result["state"]

            # Mock HTTP error
            import requests
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = requests.HTTPError("400 Bad Request")

            with patch('requests.post', return_value=mock_response):
                with pytest.raises(requests.HTTPError):
                    service.complete_session("google", state=state, code="invalid_code")


# ============================================================================
# TIER 1 - CRITICAL TESTS: Session Retrieval
# ============================================================================

class TestSessionRetrieval:
    """Test session retrieval and lookup"""

    def test_get_session_success(self):
        """Should retrieve stored session by session_id"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            provider_config = {
                "client_id": "test_client",
                "authorization_endpoint": "https://provider.com/auth",
                "token_endpoint": "https://provider.com/token",
                "redirect_uri": "http://localhost/callback"
            }
            (service.config_path / "google.json").write_text(json.dumps(provider_config))

            # Create session
            result = service.create_session("google")
            session_id = result["session_id"]

            # Retrieve session
            session = service.get_session(session_id)

            assert session is not None
            assert session["id"] == session_id
            assert session["provider"] == "google"
            assert session["status"] == "pending"

    def test_get_session_not_found(self):
        """Should return None for non-existent session"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            session = service.get_session("nonexistent_session_id")

            assert session is None

    def test_find_session_by_state_success(self):
        """Should find session by state value"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            provider_config = {
                "client_id": "test_client",
                "authorization_endpoint": "https://provider.com/auth",
                "token_endpoint": "https://provider.com/token",
                "redirect_uri": "http://localhost/callback"
            }
            (service.config_path / "google.json").write_text(json.dumps(provider_config))

            # Create session
            result = service.create_session("google")
            state = result["state"]

            # Find by state
            session_id, session = service._find_session_by_state(state)

            assert session_id == result["session_id"]
            assert session["state"] == state

    def test_find_session_by_state_not_found(self):
        """Should return empty result for unknown state"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            session_id, session = service._find_session_by_state("unknown_state")

            assert session_id == ""
            assert session is None

    def test_find_session_by_state_among_multiple(self):
        """Should find correct session among multiple sessions"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            provider_config = {
                "client_id": "test_client",
                "authorization_endpoint": "https://provider.com/auth",
                "token_endpoint": "https://provider.com/token",
                "redirect_uri": "http://localhost/callback"
            }
            (service.config_path / "google.json").write_text(json.dumps(provider_config))

            # Create multiple sessions
            session1 = service.create_session("google")
            session2 = service.create_session("google")
            session3 = service.create_session("google")

            # Find second session by state
            session_id, session = service._find_session_by_state(session2["state"])

            assert session_id == session2["session_id"]
            assert session["id"] == session2["session_id"]


# ============================================================================
# TIER 2 - DEPENDENCY FUNCTION: get_oauth_service
# ============================================================================

class TestDependencyFunction:
    """Test FastAPI dependency helper"""

    def test_get_oauth_service_returns_instance(self):
        """Should return OAuthService instance"""
        service = get_oauth_service()

        assert isinstance(service, OAuthService)
        assert hasattr(service, 'create_session')
        assert hasattr(service, 'complete_session')
        assert hasattr(service, 'get_session')


# ============================================================================
# TIER 3 - EDGE CASES: Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_create_session_provider_not_found(self):
        """Should raise FileNotFoundError for missing provider"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            with pytest.raises(FileNotFoundError):
                service.create_session("nonexistent_provider")

    def test_session_file_with_malformed_json(self):
        """Should raise JSONDecodeError when reading malformed session"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            # Create malformed session file
            session_file = service.sessions_path / "broken_session.json"
            session_file.write_text("{ invalid json")

            with pytest.raises(json.JSONDecodeError):
                service.get_session("broken_session")

    def test_complete_session_timeout(self):
        """Should handle timeout from token endpoint"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            provider_config = {
                "client_id": "test_client",
                "authorization_endpoint": "https://provider.com/auth",
                "token_endpoint": "https://provider.com/token",
                "redirect_uri": "http://localhost/callback"
            }
            (service.config_path / "google.json").write_text(json.dumps(provider_config))

            session_result = service.create_session("google")
            state = session_result["state"]

            # Mock timeout
            import requests
            with patch('requests.post', side_effect=requests.Timeout("Connection timeout")):
                with pytest.raises(requests.Timeout):
                    service.complete_session("google", state=state, code="code123")

    def test_scope_separator_custom(self):
        """Should use custom scope_separator"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            provider_config = {
                "client_id": "test_client",
                "authorization_endpoint": "https://provider.com/auth",
                "token_endpoint": "https://provider.com/token",
                "redirect_uri": "http://localhost/callback",
                "scopes": ["read", "write", "admin"],
                "scope_separator": ","  # Custom separator
            }
            (service.config_path / "google.json").write_text(json.dumps(provider_config))

            result = service.create_session("google")

            # Should use comma separator
            assert "scope=read%2Cwrite%2Cadmin" in result["authorization_url"]

    def test_scope_param_custom(self):
        """Should use custom scope_param name"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = OAuthService(base_path=Path(tmpdir))

            provider_config = {
                "client_id": "test_client",
                "authorization_endpoint": "https://provider.com/auth",
                "token_endpoint": "https://provider.com/token",
                "redirect_uri": "http://localhost/callback",
                "scopes": ["read"],
                "scope_param": "permissions"  # Custom param name
            }
            (service.config_path / "google.json").write_text(json.dumps(provider_config))

            result = service.create_session("google")

            # Should use 'permissions' instead of 'scope'
            assert "permissions=read" in result["authorization_url"]
            assert "scope=" not in result["authorization_url"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
