#!/usr/bin/env python3
"""
Camera Database Search Index
Loads all brand JSON files and builds an in-memory search index
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class CameraModel:
    """Represents a camera model from the database"""
    brand: str
    brand_id: str
    model: str
    display: str  # "Brand: Model" format
    entry: Dict[str, Any]  # Full entry data with URL patterns


class CameraIndex:
    """In-memory search index for camera models"""

    def __init__(self):
        self.models: List[CameraModel] = []
        self._loaded = False

    def load(self, data_dir: str = None):
        """Load all brand JSON files into memory"""
        if self._loaded:
            return

        if data_dir is None:
            # Default to data/brands directory relative to this file
            current_dir = Path(__file__).parent
            data_dir = current_dir / "data" / "brands"
        else:
            data_dir = Path(data_dir)

        if not data_dir.exists():
            raise FileNotFoundError(f"Camera database directory not found: {data_dir}")

        # Load all JSON files
        for json_file in data_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                brand = data.get("brand", "Unknown")
                brand_id = data.get("brand_id", "unknown")
                entries = data.get("entries", [])

                # Index each entry
                for entry in entries:
                    models = entry.get("models", [])
                    for model in models:
                        display = f"{brand}: {model}"

                        camera_model = CameraModel(
                            brand=brand,
                            brand_id=brand_id,
                            model=model,
                            display=display,
                            entry=entry
                        )
                        self.models.append(camera_model)

            except Exception as e:
                # Log but don't fail on individual file errors
                print(f"Warning: Failed to load {json_file}: {e}")
                continue

        self._loaded = True
        print(f"Loaded {len(self.models)} camera models from {len(list(data_dir.glob('*.json')))} brand files")

    def search(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search for camera models matching the query

        Args:
            query: Search string (case-insensitive)
            limit: Maximum number of results

        Returns:
            List of matching models with format:
            [{"brand": "Hikvision", "model": "2CD2032-I", "display": "Hikvision: 2CD2032-I", "entry": {...}}]
        """
        if not self._loaded:
            self.load()

        query_lower = query.lower().strip()
        if not query_lower:
            return []

        results = []
        seen_displays = set()

        # Search through all models
        for camera_model in self.models:
            # Check if query matches brand or model
            brand_lower = camera_model.brand.lower()
            model_lower = camera_model.model.lower()

            if query_lower in brand_lower or query_lower in model_lower:
                # Avoid duplicates
                if camera_model.display not in seen_displays:
                    results.append({
                        "brand": camera_model.brand,
                        "brand_id": camera_model.brand_id,
                        "model": camera_model.model,
                        "display": camera_model.display,
                        "entry": camera_model.entry
                    })
                    seen_displays.add(camera_model.display)

                if len(results) >= limit:
                    break

        # Add "Unlisted" option for each unique brand in results
        unique_brands = {}
        for result in results:
            if result["brand"] not in unique_brands:
                unique_brands[result["brand"]] = result["brand_id"]

        # Prepend unlisted options
        unlisted_options = []
        for brand, brand_id in unique_brands.items():
            unlisted_options.append({
                "brand": brand,
                "brand_id": brand_id,
                "model": "Unlisted",
                "display": f"{brand}: Unlisted",
                "entry": None
            })

        # Combine: unlisted first, then matches
        return unlisted_options + results

    def get_entries_for_model(self, brand: str, model: str) -> List[Dict[str, Any]]:
        """
        Get all URL pattern entries for a specific brand and model

        Args:
            brand: Camera brand name
            model: Camera model name

        Returns:
            List of entries with URL patterns
        """
        if not self._loaded:
            self.load()

        entries = []
        seen_entries = set()

        for camera_model in self.models:
            if camera_model.brand == brand and camera_model.model == model:
                # Avoid duplicate entries (same model might appear in multiple entries)
                entry_key = json.dumps(camera_model.entry, sort_keys=True)
                if entry_key not in seen_entries:
                    entries.append(camera_model.entry)
                    seen_entries.add(entry_key)

        return entries

    def get_popular_patterns(self) -> List[Dict[str, Any]]:
        """
        Get most popular/common stream patterns for when model is unknown

        Returns:
            List of common URL pattern entries
        """
        # Most common patterns across all cameras
        popular_patterns = [
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/live/main",
                "notes": "Common RTSP main stream"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/live/sub",
                "notes": "Common RTSP sub stream"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/stream1",
                "notes": "Generic stream 1"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/stream2",
                "notes": "Generic stream 2"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/cam/realmonitor?channel=1&subtype=0",
                "notes": "Dahua-style URL"
            },
            {
                "type": "MJPEG",
                "protocol": "http",
                "port": 80,
                "url": "/video.cgi",
                "notes": "Common MJPEG stream"
            }
        ]

        return popular_patterns


# Global singleton instance
_camera_index = None


def get_camera_index() -> CameraIndex:
    """Get or create the global camera index singleton"""
    global _camera_index
    if _camera_index is None:
        _camera_index = CameraIndex()
        _camera_index.load()
    return _camera_index


if __name__ == '__main__':
    # Test the index
    index = CameraIndex()
    index.load()

    # Test search
    results = index.search("hikvision", limit=10)
    print(f"\nSearch 'hikvision': {len(results)} results")
    for r in results[:5]:
        print(f"  - {r['display']}")

    # Test getting entries
    if results:
        first = results[0]
        entries = index.get_entries_for_model(first['brand'], first['model'])
        print(f"\nEntries for {first['display']}: {len(entries)}")
        for e in entries[:3]:
            print(f"  - {e.get('protocol')}://{e.get('url')}")
