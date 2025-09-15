"""
Generic Tools API: proxy tool execution and serve connector setup flows
"""

import os
import json
import logging
import requests
from typing import Any, Dict
from fastapi import APIRouter, HTTPException

from services.config_service import ConfigService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/integrations", tags=["Tools"])

config_service = ConfigService()


@router.get("/{integration}/setup")
async def get_integration_setup(integration: str) -> Dict[str, Any]:
    """Return connector setup.json (flows and tools metadata)"""
    try:
        setup = config_service.get_connector_setup(integration)
        if not setup:
            raise HTTPException(status_code=404, detail="Setup not found")
        return setup
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load setup for {integration}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{integration}/tools/execute")
async def execute_tool(integration: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Proxy tool execution to test_runner (isolated container)."""
    try:
        tool = body.get("tool")
        input_payload = body.get("input", {})
        if not tool:
            raise HTTPException(status_code=400, detail="Missing 'tool' field")

        test_runner_url = os.environ.get("TEST_RUNNER_URL", "http://localhost:8001")
        url = f"{test_runner_url}/actions/{integration}/execute"

        resp = requests.post(url, json={"tool": tool, "input": input_payload}, timeout=30)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=f"Tool runner error: {resp.text}")

        data = resp.json()
        # Expecting {ok: bool, result|error}
        return data
    except HTTPException:
        raise
    except requests.Timeout:
        raise HTTPException(status_code=504, detail="Tool execution timeout")
    except Exception as e:
        logger.error(f"Failed to execute tool {integration}/{body.get('tool')}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

