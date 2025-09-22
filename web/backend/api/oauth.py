"""OAuth API endpoints"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from services.oauth_service import OAuthService, get_oauth_service

router = APIRouter(prefix="/api/oauth", tags=["OAuth"])


@router.post("/{provider}/session")
async def create_oauth_session(
    provider: str,
    payload: Optional[Dict[str, Any]] = None,
    service: OAuthService = Depends(get_oauth_service)
) -> Dict[str, Any]:
    """Create an OAuth session and return the authorization URL."""
    payload = payload or {}
    try:
        session = service.create_session(provider, redirect_uri=payload.get("redirect_uri"))
        return session
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/session/{session_id}")
async def read_oauth_session(
    session_id: str,
    service: OAuthService = Depends(get_oauth_service)
) -> Dict[str, Any]:
    """Return stored session details for the frontend wizard."""
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    error_description: Optional[str] = Query(default=None),
    service: OAuthService = Depends(get_oauth_service)
) -> HTMLResponse:
    """Handle OAuth provider callback and notify the frontend window."""
    if error:
        payload = {
            "status": "error",
            "error": error,
            "description": error_description
        }
        message = json.dumps(payload)
        content = f"<script>window.opener && window.opener.postMessage({message}, '*'); window.close();</script>"
        return HTMLResponse(content=content)

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing OAuth code or state")

    try:
        session = service.complete_session(provider, state, code)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload = {
        "status": "authorized",
        "session_id": session["session_id"]
    }
    message = json.dumps(payload)
    content = f"<script>window.opener && window.opener.postMessage({message}, '*'); window.close();</script>"
    return HTMLResponse(content=content)
