"""
MQTT Device Discovery API
Allows connectors to discover devices from other "parent" connectors via MQTT
"""

import re
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from services.mqtt_service import MQTTService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mqtt", tags=["MQTT Discovery"])

# This will be set by main.py
mqtt_service: Optional[MQTTService] = None


class DiscoverDevicesRequest(BaseModel):
    """Request to discover devices from MQTT"""
    connector_type: str
    mqtt_topic_pattern: Optional[str] = None
    instance_filter: Optional[str] = None
    base_topic_override: Optional[str] = None
    search_query: Optional[str] = None


class DeviceInfo(BaseModel):
    """Device information from MQTT"""
    mqtt_path: str
    instance_id: str
    device_id: str
    state: Dict[str, Any]
    timestamp: Optional[str] = None


def extract_nested_field(obj: Any, path: str) -> Any:
    """
    Extract nested field from object using dot notation
    Example: extract_nested_field(state, 'stream_urls.mp4')
    """
    if not path or obj is None:
        return None

    parts = path.split('.')
    current = obj

    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None

        if current is None:
            return None

    return current


def matches_search_query(device_state: Dict[str, Any], query: str, searchable_fields: List[str]) -> bool:
    """
    Check if device matches search query in any of the searchable fields
    """
    if not query:
        return True

    query_lower = query.lower()

    for field_path in searchable_fields:
        value = extract_nested_field(device_state, field_path)

        if value is not None:
            # Convert to string and check if it contains query
            if query_lower in str(value).lower():
                return True

    return False


@router.post("/discover-connector-devices", response_model=List[DeviceInfo])
async def discover_connector_devices(request: DiscoverDevicesRequest):
    """
    Discover devices from other connectors via MQTT

    This endpoint scans MQTT topic cache for devices belonging to a specific connector type
    and returns them with full state information.

    Example:
    ```
    POST /api/mqtt/discover-connector-devices
    {
        "connector_type": "cameras",
        "search_query": "10.0.20",
        "instance_filter": "cameras_*"
    }
    ```

    Returns list of devices with their MQTT paths and state data.
    """
    if not mqtt_service:
        raise HTTPException(status_code=503, detail="MQTT service not available")

    if not mqtt_service.connected:
        raise HTTPException(status_code=503, detail="MQTT not connected")

    try:
        # Get base topic from config or use override
        base_topic = request.base_topic_override or mqtt_service.config.get('base_topic', 'IoT2mqtt')

        # Build pattern to match device state topics
        # Pattern: {base_topic}/v1/instances/{instance_id}/devices/{device_id}/state
        if request.mqtt_topic_pattern:
            # Use custom pattern
            pattern = request.mqtt_topic_pattern
        else:
            # Build default pattern based on connector_type
            # Match: IoT2mqtt.../v1/instances/{connector_type}_*/devices/*/state
            pattern = f"{re.escape(base_topic)}.*/v1/instances/({re.escape(request.connector_type)}_[^/]+)/devices/([^/]+)/state$"

        logger.info(f"Discovering devices with pattern: {pattern}")

        # Get all topics from cache
        topic_cache = mqtt_service.topic_cache
        devices: List[DeviceInfo] = []

        # Scan through all topics
        for topic, topic_data in topic_cache.items():
            match = re.match(pattern, topic)

            if match:
                # Extract instance_id and device_id from topic
                if request.mqtt_topic_pattern:
                    # For custom patterns, try to extract from topic path
                    parts = topic.split('/')
                    try:
                        instances_idx = parts.index('instances')
                        devices_idx = parts.index('devices')
                        instance_id = parts[instances_idx + 1]
                        device_id = parts[devices_idx + 1]
                    except (ValueError, IndexError):
                        logger.warning(f"Could not parse topic: {topic}")
                        continue
                else:
                    # Use regex groups
                    instance_id = match.group(1)
                    device_id = match.group(2)

                # Apply instance filter if provided
                if request.instance_filter:
                    instance_pattern = request.instance_filter.replace('*', '.*')
                    if not re.match(f"^{instance_pattern}$", instance_id):
                        continue

                # Get device state
                state = topic_data.get('value', {})

                if not isinstance(state, dict):
                    continue

                # Apply search query filter
                if request.search_query:
                    # Default searchable fields
                    searchable_fields = [
                        'name', 'device_id', 'ip', 'brand', 'model',
                        'friendly_name', 'manufacturer', 'serial_number'
                    ]

                    if not matches_search_query(state, request.search_query, searchable_fields):
                        continue

                # Create device info
                device_info = DeviceInfo(
                    mqtt_path=topic,
                    instance_id=instance_id,
                    device_id=device_id,
                    state=state,
                    timestamp=topic_data.get('timestamp')
                )

                devices.append(device_info)

        logger.info(f"Found {len(devices)} devices for connector '{request.connector_type}'")

        # Sort by device name or device_id
        devices.sort(key=lambda d: d.state.get('name', d.device_id))

        return devices

    except Exception as e:
        logger.error(f"Failed to discover devices: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")


@router.get("/connector-types")
async def get_available_connector_types():
    """
    Get list of available connector types from MQTT

    Returns all unique connector types found in MQTT instance topics.
    """
    if not mqtt_service:
        raise HTTPException(status_code=503, detail="MQTT service not available")

    if not mqtt_service.connected:
        raise HTTPException(status_code=503, detail="MQTT not connected")

    try:
        base_topic = mqtt_service.config.get('base_topic', 'IoT2mqtt')
        pattern = f"{re.escape(base_topic)}.*/v1/instances/([^_]+)_[^/]+/.*"

        connector_types = set()

        for topic in mqtt_service.topic_cache.keys():
            match = re.match(pattern, topic)
            if match:
                connector_type = match.group(1)
                connector_types.add(connector_type)

        return {
            "connector_types": sorted(list(connector_types))
        }

    except Exception as e:
        logger.error(f"Failed to get connector types: {e}")
        raise HTTPException(status_code=500, detail=str(e))
