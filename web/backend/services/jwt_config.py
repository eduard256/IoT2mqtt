"""
JWT Configuration Service
Provides secure JWT secret key management
"""

import os
from services.secrets_manager import SecretsManager

# JWT Algorithm
ALGORITHM = "HS256"

# Token expiration (7 days)
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

# Lazy initialization of secrets manager
_secrets_manager = None


def _get_secrets_manager() -> SecretsManager:
    """Get or create SecretsManager instance (lazy initialization)"""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager


def get_jwt_secret() -> str:
    """
    Get JWT secret key for token signing

    Priority:
    1. JWT_SECRET_KEY environment variable (if set and not default)
    2. Auto-generated secure key via SecretsManager

    Returns:
        Cryptographically secure JWT secret key

    Raises:
        Exception if unable to get or create secret
    """
    # Check environment variable first
    env_secret = os.getenv("JWT_SECRET_KEY")

    # Reject dangerous default value
    if env_secret and env_secret != "your-secret-key-change-in-production":
        return env_secret

    # Auto-generate or load existing secret
    sm = _get_secrets_manager()
    return sm.get_or_create_jwt_secret()
