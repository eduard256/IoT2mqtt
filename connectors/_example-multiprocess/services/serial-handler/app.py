#!/usr/bin/env python3
"""
Serial Handler Service - Temperature and Humidity Sensors

This service simulates reading from sensors connected via serial port.
In a real implementation, this would use pyserial to communicate with
actual hardware. Here we simulate sensor readings with realistic values
that change over time to demonstrate the service architecture.

Why this service exists:
- Demonstrates protocol-specific handler in Python
- Shows how to expose internal REST API for other services
- Simulates hardware communication patterns with error handling
- Provides example of stateful service maintaining sensor readings
"""

import os
import time
import math
import random
from datetime import datetime
from flask import Flask, jsonify
from typing import Dict, Any, Optional

app = Flask(__name__)

# Service configuration
SERVICE_PORT = int(os.getenv('SERVICE_PORT', '5001'))

# Simulated sensor state
# In real implementation, this would track serial port connections
sensor_readings = {}
sensor_errors = {}
last_update = {}

# Base values for realistic sensor simulation
BASE_TEMPERATURE = 22.0  # Celsius
BASE_HUMIDITY = 45.0     # Percentage


def simulate_sensor_reading(sensor_id: str, sensor_type: str) -> Optional[Dict[str, Any]]:
    """
    Simulate reading from a sensor.

    Uses sine waves and random noise to create realistic changing values.
    Occasionally simulates sensor errors to demonstrate error handling.

    Args:
        sensor_id: Unique sensor identifier
        sensor_type: 'temperature' or 'humidity'

    Returns:
        Dict with reading data or None if sensor error
    """
    current_time = time.time()

    # Simulate occasional sensor communication errors (5% chance)
    if random.random() < 0.05:
        sensor_errors[sensor_id] = {
            'error': 'READ_TIMEOUT',
            'message': 'Sensor did not respond within timeout period',
            'timestamp': datetime.now().isoformat()
        }
        return None

    # Clear any previous errors on successful read
    if sensor_id in sensor_errors:
        del sensor_errors[sensor_id]

    # Generate realistic values using sine wave + noise
    # This simulates daily temperature/humidity patterns
    daily_cycle = math.sin(current_time / 3600.0)  # Slow sine wave
    noise = random.gauss(0, 0.5)  # Random fluctuation

    if sensor_type == 'temperature':
        # Temperature varies ±3°C throughout the day
        value = BASE_TEMPERATURE + (daily_cycle * 3.0) + noise
        unit = '°C'
        # Temperature sensors typically accurate to 0.1°C
        value = round(value, 1)
    elif sensor_type == 'humidity':
        # Humidity varies ±10% throughout the day
        value = BASE_HUMIDITY + (daily_cycle * 10.0) + noise
        # Clamp humidity to realistic range
        value = max(20.0, min(80.0, value))
        unit = '%'
        # Humidity sensors typically accurate to 1%
        value = round(value, 1)
    else:
        return None

    reading = {
        'sensor_id': sensor_id,
        'type': sensor_type,
        'value': value,
        'unit': unit,
        'timestamp': datetime.now().isoformat(),
        'quality': 'good'  # Could be 'good', 'fair', 'poor' based on signal
    }

    # Cache the reading
    sensor_readings[sensor_id] = reading
    last_update[sensor_id] = current_time

    return reading


@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for service monitoring.

    Returns basic service status. In production, this might check
    actual serial port availability or other hardware resources.
    """
    return jsonify({
        'service': 'serial-handler',
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'sensors_tracked': len(sensor_readings),
        'errors_count': len(sensor_errors)
    })


@app.route('/sensors', methods=['GET'])
def list_sensors():
    """
    List all sensors this handler manages.

    Returns metadata about available sensors. The actual sensor
    configuration comes from the instance config loaded by MQTT bridge.
    """
    sensors = []

    # In real implementation, this would query actual hardware
    # For simulation, we return the sensors we've been asked about
    for sensor_id in sensor_readings.keys():
        reading = sensor_readings[sensor_id]
        sensors.append({
            'sensor_id': sensor_id,
            'type': reading['type'],
            'last_update': last_update.get(sensor_id),
            'status': 'online' if sensor_id not in sensor_errors else 'error'
        })

    return jsonify({
        'sensors': sensors,
        'count': len(sensors)
    })


@app.route('/sensor/<sensor_id>', methods=['GET'])
def get_sensor_reading(sensor_id: str):
    """
    Get current reading from a specific sensor.

    This performs an actual read operation (or simulates one).
    Called by state aggregator when fresh data is needed.

    Args:
        sensor_id: Unique sensor identifier from URL path

    Returns:
        Current sensor reading or error information
    """
    # Determine sensor type from sensor_id pattern
    # In real implementation, this would come from configuration
    if 'temp' in sensor_id.lower():
        sensor_type = 'temperature'
    elif 'humidity' in sensor_id.lower():
        sensor_type = 'humidity'
    else:
        return jsonify({
            'error': 'UNKNOWN_SENSOR',
            'message': f'Sensor {sensor_id} not configured'
        }), 404

    # Simulate reading from sensor
    reading = simulate_sensor_reading(sensor_id, sensor_type)

    if reading is None:
        # Sensor error occurred
        error = sensor_errors.get(sensor_id, {
            'error': 'READ_FAILED',
            'message': 'Unknown read error'
        })
        return jsonify(error), 503  # Service Unavailable

    return jsonify(reading)


@app.route('/sensor/<sensor_id>/cached', methods=['GET'])
def get_cached_reading(sensor_id: str):
    """
    Get cached reading without performing new read.

    Useful for reducing load on sensor hardware when
    frequent polling is not necessary.

    Returns cached reading if available, 404 if no cache exists.
    """
    if sensor_id not in sensor_readings:
        return jsonify({
            'error': 'NO_CACHE',
            'message': f'No cached reading for sensor {sensor_id}'
        }), 404

    reading = sensor_readings[sensor_id].copy()
    reading['cached'] = True
    reading['cache_age'] = time.time() - last_update[sensor_id]

    return jsonify(reading)


@app.route('/errors', methods=['GET'])
def get_errors():
    """
    Get current sensor errors.

    Useful for diagnostics and monitoring.
    Errors are automatically cleared on next successful read.
    """
    return jsonify({
        'errors': sensor_errors,
        'count': len(sensor_errors),
        'timestamp': datetime.now().isoformat()
    })


if __name__ == '__main__':
    print(f"Starting Serial Handler Service on port {SERVICE_PORT}")
    print("This service simulates serial-connected temperature and humidity sensors")
    print(f"Health check: http://localhost:{SERVICE_PORT}/health")

    # Run Flask in production mode with Werkzeug server
    # In production, use gunicorn or uwsgi for better performance
    app.run(
        host='0.0.0.0',
        port=SERVICE_PORT,
        debug=False,
        threaded=True  # Handle concurrent requests
    )
