"""OAuth coordination utilities"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests


class OAuthService:
    """Manage OAuth provider metadata and authorization sessions."""

    def __init__(self, base_path: Optional[Path] = None) -> None:
        raw_base = base_path or Path(os.getenv("IOT2MQTT_PATH", Path(__file__).resolve().parents[2]))
        self.base_path = Path(raw_base).resolve()
        self.config_path = self.base_path / "config" / "oauth"
        self.sessions_path = self.base_path / "oauth_sessions"
        self.config_path.mkdir(parents=True, exist_ok=True)
        self.sessions_path.mkdir(parents=True, exist_ok=True)

    def load_provider(self, provider: str) -> Dict[str, Any]:
        """Return provider configuration or raise FileNotFoundError."""
        config_file = self.config_path / f"{provider}.json"
        if not config_file.exists():
            raise FileNotFoundError(f"OAuth provider '{provider}' is not configured")
        with open(config_file, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def create_session(self, provider: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
        """Create new OAuth session and return metadata including authorize URL."""
        provider_cfg = self.load_provider(provider)
        session_id = uuid.uuid4().hex
        state = uuid.uuid4().hex
        redirect = redirect_uri or provider_cfg.get("redirect_uri")
        if not redirect:
            raise ValueError("Redirect URI must be specified either in the request or provider config")

        scope = provider_cfg.get("scopes", [])
        scope_param = provider_cfg.get("scope_separator", " ").join(scope) if scope else ""
        params = {
            "response_type": "code",
            "client_id": provider_cfg["client_id"],
            "redirect_uri": redirect,
            "state": state
        }
        if scope_param:
            params[provider_cfg.get("scope_param", "scope")] = scope_param
        for key, value in provider_cfg.get("extra_authorize_params", {}).items():
            params[key] = value

        from urllib.parse import urlencode

        authorize_url = f"{provider_cfg['authorization_endpoint']}?{urlencode(params)}"
        from datetime import datetime

        session_record = {
            "id": session_id,
            "provider": provider,
            "state": state,
            "redirect_uri": redirect,
            "status": "pending",
            "issued_at": datetime.utcnow().isoformat(),
            "tokens": None
        }
        self._write_session(session_id, session_record)
        return {"session_id": session_id, "state": state, "authorization_url": authorize_url}

    def complete_session(self, provider: str, state: str, code: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens and store them inside the session."""
        session_id, session = self._find_session_by_state(state)
        if session is None or session["provider"] != provider:
            raise LookupError("Unknown or mismatched OAuth session")
        provider_cfg = self.load_provider(provider)
        token_endpoint = provider_cfg["token_endpoint"]
        redirect_uri = session["redirect_uri"]

        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": provider_cfg["client_id"],
            "client_secret": provider_cfg.get("client_secret", ""),
            "redirect_uri": redirect_uri
        }
        response = requests.post(token_endpoint, data=payload, timeout=30)
        response.raise_for_status()
        tokens = response.json()
        session["status"] = "authorized"
        session["tokens"] = tokens
        self._write_session(session_id, session)
        return {"session_id": session_id, "tokens": tokens}

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return stored session without mutating it."""
        path = self.sessions_path / f"{session_id}.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data

    def _find_session_by_state(self, state: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        for session_file in self.sessions_path.glob("*.json"):
            with open(session_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
                if data.get("state") == state:
                    return session_file.stem, data
        return "", None

    def _write_session(self, session_id: str, payload: Dict[str, Any]) -> None:
        path = self.sessions_path / f"{session_id}.json"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)


def get_oauth_service() -> OAuthService:
    """FastAPI dependency helper."""
    return OAuthService()
