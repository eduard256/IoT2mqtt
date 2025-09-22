"""Connector template showing the minimal structure expected by IoT2MQTT."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'shared'))

from base_connector import BaseConnector

logger = logging.getLogger(__name__)


class Connector(BaseConnector):
    """Example connector used as a starting point."""

    def initialize_connection(self) -> None:
        """Establish connections to external systems."""
        # TODO: Add initialization logic
        logger.info("initialize_connection called with config: %s", self.config)

    def cleanup_connection(self) -> None:
        """Clean up resources before shutdown."""
        # TODO: Add cleanup logic
        logger.info("cleanup_connection executed")

    def get_device_state(self, device_id: str, device_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return the latest device state."""
        # TODO: Replace with real state retrieval
        return {
            "online": True,
            "last_update": self.now_iso(),
            "sample": "value"
        }

    def apply_device_command(self, device_id: str, device_config: Dict[str, Any], command: Dict[str, Any]) -> None:
        """Handle device command coming from MQTT."""
        # TODO: Implement device command logic
        logger.info("Received command for %s: %s", device_id, command)

    def now_iso(self) -> str:
        from datetime import datetime
        return datetime.utcnow().isoformat()
