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
        Search for camera models matching the query with intelligent scoring

        Args:
            query: Search string (case-insensitive)
                   Supports formats:
                   - "brand" → all models of brand
                   - "model" → all brands with this model
                   - "brand: model" → specific brand+model combination
                   - "brand model" → fuzzy search in both fields
            limit: Maximum number of results

        Returns:
            List of matching models sorted by relevance:
            [{"brand": "Hikvision", "model": "2CD2032-I", "display": "Hikvision: 2CD2032-I", "entry": {...}, "score": 90}]
        """
        if not self._loaded:
            self.load()

        query_normalized = query.lower().strip()
        if not query_normalized:
            return []

        # Parse query based on presence of colon separator
        has_colon = ':' in query_normalized

        if has_colon:
            # Explicit brand:model format
            parts = query_normalized.split(':', 1)
            brand_query = parts[0].strip()
            model_query = parts[1].strip() if len(parts) > 1 else ''
        else:
            # Single query - will search across all fields
            brand_query = None
            model_query = None

        results_with_scores = []
        seen_displays = set()

        # Search through all models
        for camera_model in self.models:
            brand_lower = camera_model.brand.lower()
            model_lower = camera_model.model.lower()
            display_lower = camera_model.display.lower()

            score = 0

            if has_colon:
                # Colon-separated query: strict brand+model matching
                brand_match = brand_query in brand_lower if brand_query else True
                model_match = model_query in model_lower if model_query else True

                if not brand_match:
                    continue
                if not model_match:
                    continue

                # Calculate score for colon queries
                if brand_query and brand_lower == brand_query:
                    score += 50  # Exact brand match
                elif brand_query and brand_lower.startswith(brand_query):
                    score += 40  # Brand starts with query
                elif brand_query:
                    score += 30  # Brand contains query

                if model_query and model_lower == model_query:
                    score += 50  # Exact model match
                elif model_query and model_lower.startswith(model_query):
                    score += 40  # Model starts with query
                elif model_query:
                    score += 30  # Model contains query

                # If no model specified after colon, all models of brand get same score
                if not model_query:
                    score = max(score, 30)

            else:
                # No colon: intelligent multi-field search with scoring

                # Priority 1: Exact match in display (highest relevance)
                if query_normalized == display_lower:
                    score = 100

                # Priority 2: Exact match in brand
                elif query_normalized == brand_lower:
                    score = 90

                # Priority 3: Exact match in model
                elif query_normalized == model_lower:
                    score = 80

                # Priority 4: Brand starts with query
                elif brand_lower.startswith(query_normalized):
                    score = 70

                # Priority 5: Model starts with query
                elif model_lower.startswith(query_normalized):
                    score = 60

                # Priority 6: Brand contains query
                elif query_normalized in brand_lower:
                    score = 50

                # Priority 7: Model contains query
                elif query_normalized in model_lower:
                    score = 40

                # Priority 8: Display contains query (lowest, but still relevant)
                elif query_normalized in display_lower:
                    score = 30

                # Priority 9: Multi-token search (e.g., "trassir 2141")
                # Check if all tokens in query appear in display
                elif ' ' in query_normalized:
                    tokens = query_normalized.split()
                    if all(token in display_lower for token in tokens):
                        score = 35  # Between display contains and model contains
                    else:
                        continue

                # No match - skip this model
                else:
                    continue

            # Avoid duplicates
            if camera_model.display in seen_displays:
                continue

            seen_displays.add(camera_model.display)
            results_with_scores.append({
                "brand": camera_model.brand,
                "brand_id": camera_model.brand_id,
                "model": camera_model.model,
                "display": camera_model.display,
                "entry": camera_model.entry,
                "score": score
            })

        # Sort by score (descending) - highest relevance first
        results_with_scores.sort(key=lambda x: x['score'], reverse=True)

        # Apply limit
        results_with_scores = results_with_scores[:limit]

        # Remove score from final results (internal use only)
        results = []
        for item in results_with_scores:
            result = {k: v for k, v in item.items() if k != 'score'}
            results.append(result)

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

        # Combine: unlisted first, then matches sorted by relevance
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
            List of common URL pattern entries (~50 most popular patterns)
        """
        # Most common patterns across all cameras
        # Organized by priority and popularity
        popular_patterns = [
            # === ONVIF Generic (Priority 1) ===
            {
                "type": "ONVIF",
                "protocol": "rtsp",
                "port": 554,
                "url": "/onvif1",
                "notes": "ONVIF Profile S stream 1"
            },
            {
                "type": "ONVIF",
                "protocol": "rtsp",
                "port": 554,
                "url": "/onvif2",
                "notes": "ONVIF Profile S stream 2"
            },

            # === Hikvision (Very Popular - Priority 2) ===
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/Streaming/Channels/101",
                "notes": "Hikvision main stream (HD)"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/Streaming/Channels/102",
                "notes": "Hikvision sub stream (SD)"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/Streaming/Channels/1/httppreview",
                "notes": "Hikvision HTTP preview"
            },
            {
                "type": "MJPEG",
                "protocol": "http",
                "port": 80,
                "url": "/ISAPI/Streaming/channels/101/picture",
                "notes": "Hikvision snapshot"
            },

            # === Dahua (Very Popular - Priority 2) ===
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/cam/realmonitor?channel=1&subtype=0",
                "notes": "Dahua main stream"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/cam/realmonitor?channel=1&subtype=1",
                "notes": "Dahua sub stream"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif",
                "notes": "Dahua ONVIF compatible"
            },

            # === Generic RTSP Patterns (Priority 3) ===
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
                "url": "/h264",
                "notes": "H264 stream path"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/h264Preview_01_main",
                "notes": "H264 preview main"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/h264Preview_01_sub",
                "notes": "H264 preview sub"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/ch01/0",
                "notes": "Channel 1 main"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/ch01/1",
                "notes": "Channel 1 sub"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/live",
                "notes": "Simple live stream"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/video",
                "notes": "Simple video stream"
            },

            # === Axis (Popular) ===
            {
                "type": "MJPEG",
                "protocol": "http",
                "port": 80,
                "url": "/axis-cgi/mjpg/video.cgi",
                "notes": "Axis MJPEG stream"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/axis-media/media.amp",
                "notes": "Axis RTSP stream"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/axis-media/media.amp?videocodec=h264",
                "notes": "Axis H264 stream"
            },

            # === Foscam (Popular) ===
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/videoMain",
                "notes": "Foscam main stream"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/videoSub",
                "notes": "Foscam sub stream"
            },
            {
                "type": "MJPEG",
                "protocol": "http",
                "port": 88,
                "url": "/cgi-bin/CGIStream.cgi?cmd=GetMJStream",
                "notes": "Foscam MJPEG (port 88)"
            },
            {
                "type": "JPEG",
                "protocol": "http",
                "port": 88,
                "url": "/cgi-bin/CGIProxy.fcgi?cmd=snapPicture2",
                "notes": "Foscam snapshot"
            },

            # === TP-Link/Tapo ===
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/stream1",
                "notes": "TP-Link stream 1"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/stream2",
                "notes": "TP-Link stream 2"
            },

            # === Amcrest (Dahua-based) ===
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/cam/realmonitor?channel=1&subtype=00",
                "notes": "Amcrest main (Dahua variant)"
            },

            # === Generic with Credentials in Query String ===
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/live?user={username}&password={password}",
                "notes": "Generic with query credentials"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/stream?usr={username}&pwd={password}",
                "notes": "Generic alt credentials format"
            },

            # === MJPEG/HTTP Streams (Priority 4) ===
            {
                "type": "MJPEG",
                "protocol": "http",
                "port": 80,
                "url": "/video.cgi",
                "notes": "Common MJPEG stream"
            },
            {
                "type": "MJPEG",
                "protocol": "http",
                "port": 80,
                "url": "/mjpg/video.mjpg",
                "notes": "MJPEG video path"
            },
            {
                "type": "MJPEG",
                "protocol": "http",
                "port": 80,
                "url": "/cgi-bin/video.cgi",
                "notes": "CGI MJPEG stream"
            },
            {
                "type": "JPEG",
                "protocol": "http",
                "port": 80,
                "url": "/snapshot.cgi",
                "notes": "Snapshot CGI"
            },
            {
                "type": "JPEG",
                "protocol": "http",
                "port": 80,
                "url": "/cgi-bin/snapshot.cgi",
                "notes": "CGI snapshot"
            },

            # === Additional Generic Paths ===
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/1",
                "notes": "Simple path /1"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/11",
                "notes": "Simple path /11"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/mpeg4",
                "notes": "MPEG4 stream"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/mpeg4/media.amp",
                "notes": "MPEG4 media"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/live.sdp",
                "notes": "SDP live stream"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/av0_0",
                "notes": "AV stream 0_0"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/av0_1",
                "notes": "AV stream 0_1"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/channel1",
                "notes": "Channel 1"
            },
            {
                "type": "FFMPEG",
                "protocol": "rtsp",
                "port": 554,
                "url": "/media/video1",
                "notes": "Media video 1"
            },
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
