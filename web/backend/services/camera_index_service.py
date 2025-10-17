"""
Camera Index Service
Provides search functionality for camera database
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add connectors directory to path
CONNECTORS_DIR = Path(__file__).parent.parent.parent.parent / "connectors"
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

        Args:
            brand: Camera brand
            model: Camera model

        Returns:
            List of URL pattern entries
        """
        if model == "Unlisted":
            return self.index.get_popular_patterns()

        return self.index.get_entries_for_model(brand, model)
