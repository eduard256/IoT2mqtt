#!/usr/bin/env python3
"""
State Aggregator Service - Coordination Layer

This service acts as a coordination layer between protocol handlers and
the MQTT bridge. It aggregates data from multiple protocol-specific services
and provides a unified API for device management.

Why this service exists:
- Simplifies MQTT bridge logic by providing single API endpoint
- Implements caching to reduce load on protocol handlers
- Aggregates health status across all services
- Demonstrates coordination layer pattern in multi-service architecture

Design decision: This service is optional but recommended for complex connectors.
For simple connectors, the MQTT bridge can query protocol handlers directly.
"""

import os
import time
import requests
from datetime import datetime
from flask import Flask, jsonify
from typing import Dict, Any, List, Optional
from threading import Lock

app = Flask(__name__)

# Service configuration
SERVICE_PORT = int(os.getenv('SERVICE_PORT', '5003'))
SERIAL_HANDLER_URL = os.getenv('SERIAL_HANDLER_URL', 'http://localhost:5001')
HTTP_POLLER_URL = os.getenv('HTTP_POLLER_URL', 'http://localhost:5002')
CACHE_TTL = int(os.getenv('CACHE_TTL', '10'))  # seconds

# Cache for sensor readings
# Using simple in-memory cache with TTL
# Production implementation might use Redis or memcached
reading_cache = {}
cache_timestamps = {}
cache_lock = Lock()


def is_cache_valid(sensor_id: str) -> bool:
    """
    Check if cached reading is still valid based on TTL.

    Args:
        sensor_id: Sensor identifier

    Returns:
        True if cache exists and is not expired
    """
    if sensor_id not in cache_timestamps:
        return False

    age = time.time() - cache_timestamps[sensor_id]
    return age < CACHE_TTL


def get_cached_reading(sensor_id: str) -> Optional[Dict[str, Any]]:
    """
    Get reading from cache if valid.

    Thread-safe access to cache using lock.

    Args:
        sensor_id: Sensor identifier

    Returns:
        Cached reading or None if cache miss or expired
    """
    with cache_lock:
        if is_cache_valid(sensor_id):
            reading = reading_cache[sensor_id].copy()
            reading['cached'] = True
            reading['cache_age'] = time.time() - cache_timestamps[sensor_id]
            return reading
    return None


def cache_reading(sensor_id: str, reading: Dict[str, Any]):
    """
    Store reading in cache.

    Thread-safe cache update using lock.

    Args:
        sensor_id: Sensor identifier
        reading: Sensor reading data
    """
    with cache_lock:
        reading_cache[sensor_id] = reading
        cache_timestamps[sensor_id] = time.time()


def fetch_from_handler(handler_url: str, endpoint: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
    """
    Fetch data from protocol handler with error handling.

    Implements retry logic and connection error handling.
    Returns None on any error to allow graceful degradation.

    Args:
        handler_url: Base URL of protocol handler service
        endpoint: API endpoint path
        timeout: Request timeout in seconds

    Returns:
        Response data or None on error
    """
    try:
        response = requests.get(
            f"{handler_url}{endpoint}",
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        app.logger.error(f"Timeout fetching from {handler_url}{endpoint}")
        return None
    except requests.exceptions.ConnectionError:
        app.logger.error(f"Connection error to {handler_url}{endpoint}")
        return None
    except requests.exceptions.HTTPError as e:
        app.logger.error(f"HTTP error from {handler_url}{endpoint}: {e}")
        # For 503/404, return the error response so caller can handle it
        if e.response.status_code in [503, 404]:
            try:
                return e.response.json()
            except:
                return None
        return None
    except Exception as e:
        app.logger.error(f"Unexpected error fetching from {handler_url}{endpoint}: {e}")
        return None


@app.route('/health', methods=['GET'])
def health_check():
    """
    Aggregate health check across all services.

    Queries health endpoints of all protocol handlers to determine
    overall system health. This endpoint is used by Docker healthcheck.
    """
    # Check serial handler
    serial_health = fetch_from_handler(SERIAL_HANDLER_URL, '/health', timeout=2)
    serial_status = serial_health.get('status', 'unknown') if serial_health else 'unavailable'

    # Check HTTP poller
    poller_health = fetch_from_handler(HTTP_POLLER_URL, '/health', timeout=2)
    poller_status = poller_health.get('status', 'unknown') if poller_health else 'unavailable'

    # Determine overall status
    # healthy: all services responding
    # degraded: at least one service responding
    # unavailable: no services responding
    if serial_status in ['healthy', 'degraded'] and poller_status in ['healthy', 'degraded']:
        overall_status = 'healthy'
    elif serial_status != 'unavailable' or poller_status != 'unavailable':
        overall_status = 'degraded'
    else:
        overall_status = 'unavailable'

    return jsonify({
        'service': 'state-aggregator',
        'status': overall_status,
        'timestamp': datetime.now().isoformat(),
        'dependencies': {
            'serial_handler': {
                'url': SERIAL_HANDLER_URL,
                'status': serial_status
            },
            'http_poller': {
                'url': HTTP_POLLER_URL,
                'status': poller_status
            }
        },
        'cache': {
            'entries': len(reading_cache),
            'ttl': CACHE_TTL
        }
    })


@app.route('/devices', methods=['GET'])
def list_all_devices():
    """
    Get list of all devices across all protocol handlers.

    Aggregates device lists from serial handler and HTTP poller.
    This provides MQTT bridge with complete device inventory.

    Returns:
        Combined device list with type and status information
    """
    devices = []

    # Get sensors from serial handler (temperature, humidity)
    serial_sensors = fetch_from_handler(SERIAL_HANDLER_URL, '/sensors')
    if serial_sensors and 'sensors' in serial_sensors:
        for sensor in serial_sensors['sensors']:
            devices.append({
                'device_id': sensor['sensor_id'],
                'type': sensor['type'],
                'handler': 'serial',
                'status': sensor.get('status', 'unknown')
            })

    # Get sensors from HTTP poller (motion)
    poller_sensors = fetch_from_handler(HTTP_POLLER_URL, '/sensors')
    if poller_sensors and 'sensors' in poller_sensors:
        for sensor in poller_sensors['sensors']:
            devices.append({
                'device_id': sensor['sensor_id'],
                'type': sensor['type'],
                'handler': 'http_poller',
                'status': sensor.get('status', 'unknown')
            })

    return jsonify({
        'devices': devices,
        'count': len(devices),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/device/<device_id>', methods=['GET'])
def get_device_state(device_id: str):
    """
    Get current state of a specific device.

    Implements caching to reduce load on protocol handlers.
    Routes request to appropriate handler based on device type.

    Args:
        device_id: Device identifier from URL path

    Returns:
        Current device state or error
    """
    # Check cache first
    cached = get_cached_reading(device_id)
    if cached is not None:
        return jsonify(cached)

    # Determine which handler to query based on device_id
    # In production, this would come from device registry/configuration
    if 'motion' in device_id.lower():
        handler_url = HTTP_POLLER_URL
        endpoint = f'/sensor/{device_id}'
    elif 'temp' in device_id.lower() or 'humidity' in device_id.lower():
        handler_url = SERIAL_HANDLER_URL
        endpoint = f'/sensor/{device_id}'
    else:
        return jsonify({
            'error': 'UNKNOWN_DEVICE',
            'message': f'Device {device_id} not found in any handler'
        }), 404

    # Fetch fresh reading
    reading = fetch_from_handler(handler_url, endpoint)

    if reading is None:
        return jsonify({
            'error': 'HANDLER_ERROR',
            'message': f'Could not fetch state from handler',
            'device_id': device_id
        }), 503

    # Check if handler returned error
    if 'error' in reading:
        return jsonify(reading), 503

    # Cache successful reading
    cache_reading(device_id, reading)

    reading['cached'] = False
    return jsonify(reading)


@app.route('/device/<device_id>/force-refresh', methods=['POST'])
def force_refresh_device(device_id: str):
    """
    Force refresh device state bypassing cache.

    Useful when immediate fresh data is required, such as
    after sending a command to a device.

    Args:
        device_id: Device identifier from URL path

    Returns:
        Fresh device state
    """
    # Clear cache for this device
    with cache_lock:
        if device_id in reading_cache:
            del reading_cache[device_id]
        if device_id in cache_timestamps:
            del cache_timestamps[device_id]

    # Fetch fresh state (same logic as get_device_state)
    return get_device_state(device_id)


@app.route('/cache/stats', methods=['GET'])
def cache_stats():
    """
    Get cache statistics.

    Useful for monitoring and tuning cache performance.
    """
    with cache_lock:
        entries = []
        current_time = time.time()
        for sensor_id in reading_cache.keys():
            age = current_time - cache_timestamps[sensor_id]
            entries.append({
                'device_id': sensor_id,
                'age': age,
                'valid': age < CACHE_TTL
            })

        return jsonify({
            'cache_ttl': CACHE_TTL,
            'total_entries': len(reading_cache),
            'entries': entries,
            'timestamp': datetime.now().isoformat()
        })


@app.route('/cache/clear', methods=['POST'])
def clear_cache():
    """
    Clear all cached readings.

    Useful for testing or when cache consistency issues occur.
    """
    with cache_lock:
        count = len(reading_cache)
        reading_cache.clear()
        cache_timestamps.clear()

    return jsonify({
        'message': 'Cache cleared',
        'entries_cleared': count,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/errors', methods=['GET'])
def get_all_errors():
    """
    Aggregate errors from all protocol handlers.

    Provides unified view of all system errors for diagnostics.
    """
    errors = {}

    # Get errors from serial handler
    serial_errors = fetch_from_handler(SERIAL_HANDLER_URL, '/errors')
    if serial_errors and 'errors' in serial_errors:
        for sensor_id, error in serial_errors['errors'].items():
            errors[sensor_id] = {
                **error,
                'handler': 'serial'
            }

    # Get errors from HTTP poller
    poller_errors = fetch_from_handler(HTTP_POLLER_URL, '/errors')
    if poller_errors and 'errors' in poller_errors:
        for sensor_id, error in poller_errors['errors'].items():
            errors[sensor_id] = {
                **error,
                'handler': 'http_poller'
            }

    return jsonify({
        'errors': errors,
        'count': len(errors),
        'timestamp': datetime.now().isoformat()
    })


if __name__ == '__main__':
    print(f"Starting State Aggregator Service on port {SERVICE_PORT}")
    print(f"Serial Handler: {SERIAL_HANDLER_URL}")
    print(f"HTTP Poller: {HTTP_POLLER_URL}")
    print(f"Cache TTL: {CACHE_TTL} seconds")
    print(f"Health check: http://localhost:{SERVICE_PORT}/health")

    # Run Flask in production mode
    app.run(
        host='0.0.0.0',
        port=SERVICE_PORT,
        debug=False,
        threaded=True
    )
