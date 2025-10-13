#!/usr/bin/env python3
"""
Python Backend Service - Example HTTP API

This service demonstrates running an additional Python process alongside
the MQTT bridge. It exposes a simple HTTP REST API that the bridge calls
to coordinate device operations.

In a real connector, this service would:
- Communicate with hardware/devices
- Process data streams
- Run complex algorithms
- Interface with external APIs
"""

import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask application
app = Flask(__name__)

# Service configuration
SERVICE_PORT = int(os.getenv('SERVICE_PORT', 5001))

# Internal state (in real connector, this would be device state)
service_state = {
    'status': 'running',
    'started_at': datetime.now().isoformat(),
    'request_count': 0,
    'last_command': None
}


@app.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint
    Used by MQTT bridge to verify service is running
    """
    return jsonify({
        'status': 'healthy',
        'service': 'python-service',
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/status', methods=['POST'])
def status():
    """
    Get current service status
    Called by MQTT bridge during polling to gather device state

    In a real connector, this would:
    - Query device status
    - Read sensor values
    - Check connection health
    """
    service_state['request_count'] += 1

    return jsonify({
        'status': service_state['status'],
        'started_at': service_state['started_at'],
        'request_count': service_state['request_count'],
        'last_command': service_state['last_command'],
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/command', methods=['POST'])
def command():
    """
    Execute a command
    Called by MQTT bridge when MQTT commands are received

    In a real connector, this would:
    - Send commands to devices
    - Configure device parameters
    - Trigger device actions
    """
    try:
        data = request.get_json() or {}
        logger.info(f"Received command: {data}")

        # Store last command
        service_state['last_command'] = {
            'data': data,
            'timestamp': datetime.now().isoformat()
        }

        # Simulate command processing
        # In real connector: send to device, wait for response, etc.

        return jsonify({
            'success': True,
            'message': 'Command processed successfully',
            'command': data,
            'timestamp': datetime.now().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error processing command: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/reset', methods=['POST'])
def reset():
    """
    Reset service state (example of service-specific endpoint)
    """
    service_state['request_count'] = 0
    service_state['last_command'] = None

    logger.info("Service state reset")

    return jsonify({
        'success': True,
        'message': 'Service state reset'
    }), 200


def main():
    """Start the HTTP service"""
    logger.info("=" * 60)
    logger.info("Python Backend Service Starting")
    logger.info("=" * 60)
    logger.info(f"Port: {SERVICE_PORT}")

    # Run Flask app
    # Note: In production, use a proper WSGI server (gunicorn, uwsgi)
    # For this template, Flask's built-in server is sufficient
    app.run(
        host='0.0.0.0',
        port=SERVICE_PORT,
        debug=False,
        use_reloader=False  # Disable reloader in supervisor context
    )


if __name__ == '__main__':
    main()
