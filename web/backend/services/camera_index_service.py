"""
Camera Index Service
Provides search functionality for camera database
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add connectors directory to path
# Use IOT2MQTT_PATH environment variable for Docker compatibility
IOT2MQTT_PATH = os.getenv("IOT2MQTT_PATH", "/app")
CONNECTORS_DIR = Path(IOT2MQTT_PATH) / "connectors"
sys.path.insert(0, str(CONNECTORS_DIR))

from cameras.camera_index import get_camera_index


class CameraIndexService:
    """Service for searching camera models"""

    def __init__(self):
        self.index = get_camera_index()

    def search(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search for camera models

        Args:
            query: Search string
            limit: Max results

        Returns:
            List of matching models
        """
        return self.index.search(query, limit)

    def get_entries(self, brand: str, model: str) -> List[Dict[str, Any]]:
        """
        Get URL pattern entries for a specific model

        Logic:
        - If model == "Unlisted": Returns ONLY popular patterns
          (Scanner will test: ONVIF → Popular Patterns)
        - If model is selected: Returns database patterns for that model
          (Scanner will test: ONVIF → DB Patterns → Popular Patterns)

        Args:
            brand: Camera brand
            model: Camera model

        Returns:
            List of URL pattern entries
        """
        if model == "Unlisted":
            # User did NOT select a device
            # Return ONLY popular patterns (no database patterns)
            # Scanner will automatically test ONVIF first, then these patterns
            return self.index.get_popular_patterns()

        # User selected a specific model
        # Return database patterns for this brand/model
        # Scanner will automatically test ONVIF first, then these patterns,
        # then popular patterns (if < 7 streams found)
        return self.index.get_entries_for_model(brand, model)
