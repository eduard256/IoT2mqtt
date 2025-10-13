#!/usr/bin/env node
/**
 * HTTP Poller Service - Motion Detector Sensors
 *
 * This service simulates polling motion detectors that expose HTTP endpoints.
 * In a real implementation, this would poll actual network-connected sensors
 * using their HTTP APIs. Here we simulate the polling behavior and sensor
 * responses to demonstrate the service architecture.
 *
 * Why this service exists:
 * - Demonstrates protocol-specific handler in Node.js
 * - Shows async HTTP polling patterns with error handling
 * - Illustrates health monitoring and connection state management
 * - Provides example of Node.js service integration in multi-process setup
 */

const express = require('express');
const axios = require('axios');

// Service configuration
const SERVICE_PORT = parseInt(process.env.SERVICE_PORT || '5002');
const POLL_INTERVAL = parseInt(process.env.POLL_INTERVAL || '5000'); // milliseconds

// Create Express app
const app = express();
app.use(express.json());

// Sensor state tracking
// In real implementation, these would be actual sensor HTTP endpoints
const sensorStates = new Map();
const sensorHealth = new Map();
const sensorErrors = new Map();

/**
 * Simulate motion sensor HTTP endpoint response
 *
 * In production, this would be an actual axios.get() call to sensor hardware.
 * The simulation creates realistic motion detection patterns with occasional
 * false positives and sensor communication errors.
 *
 * @param {string} sensorId - Unique sensor identifier
 * @returns {Promise<Object>} Sensor reading or error
 */
async function pollMotionSensor(sensorId) {
    // Simulate network latency (50-200ms)
    await new Promise(resolve => setTimeout(resolve, 50 + Math.random() * 150));

    // Simulate occasional network errors (3% chance)
    if (Math.random() < 0.03) {
        throw new Error('NETWORK_TIMEOUT: Sensor did not respond');
    }

    // Simulate motion detection pattern
    // Motion detected randomly but with realistic patterns
    // - Higher probability during simulated "active hours"
    // - Motion events last for several seconds
    const hour = new Date().getHours();
    const isActiveHour = hour >= 8 && hour <= 22; // 8 AM to 10 PM

    // Check if we have recent motion for this sensor
    const existingState = sensorStates.get(sensorId);
    const currentTime = Date.now();

    let motionDetected = false;

    if (existingState && existingState.motion_detected) {
        // If motion was recently detected, maintain it for 10-30 seconds
        const motionDuration = currentTime - existingState.motion_start_time;
        if (motionDuration < 10000 + Math.random() * 20000) {
            motionDetected = true;
        }
    }

    // New motion detection chance (higher during active hours)
    if (!motionDetected) {
        const detectionProbability = isActiveHour ? 0.1 : 0.02;
        motionDetected = Math.random() < detectionProbability;
    }

    // Simulate sensor response format
    return {
        sensor_id: sensorId,
        type: 'motion',
        motion_detected: motionDetected,
        motion_start_time: motionDetected ? (existingState?.motion_start_time || currentTime) : null,
        sensitivity: 'medium', // Could be 'low', 'medium', 'high'
        battery_level: 85 + Math.random() * 15, // Simulate battery drain
        signal_strength: -45 - Math.random() * 30, // dBm
        timestamp: new Date().toISOString()
    };
}

/**
 * Update health status for a sensor
 *
 * Tracks connection success/failure for monitoring and diagnostics
 *
 * @param {string} sensorId - Unique sensor identifier
 * @param {boolean} success - Whether the poll was successful
 * @param {string} error - Error message if poll failed
 */
function updateSensorHealth(sensorId, success, error = null) {
    const health = sensorHealth.get(sensorId) || {
        sensor_id: sensorId,
        consecutive_failures: 0,
        consecutive_successes: 0,
        total_polls: 0,
        total_failures: 0,
        last_success: null,
        last_failure: null,
        status: 'unknown'
    };

    health.total_polls++;

    if (success) {
        health.consecutive_successes++;
        health.consecutive_failures = 0;
        health.last_success = new Date().toISOString();
        health.status = 'online';
        sensorErrors.delete(sensorId);
    } else {
        health.consecutive_failures++;
        health.consecutive_successes = 0;
        health.total_failures++;
        health.last_failure = new Date().toISOString();
        health.status = health.consecutive_failures >= 3 ? 'offline' : 'degraded';
        sensorErrors.set(sensorId, {
            error: 'POLL_FAILED',
            message: error || 'Unknown error',
            timestamp: new Date().toISOString()
        });
    }

    sensorHealth.set(sensorId, health);
}

/**
 * Poll a single sensor and update state
 *
 * This function wraps the actual polling logic with error handling
 * and state management. Called by the polling loop for each sensor.
 *
 * @param {string} sensorId - Unique sensor identifier
 */
async function pollSensor(sensorId) {
    try {
        const reading = await pollMotionSensor(sensorId);
        sensorStates.set(sensorId, reading);
        updateSensorHealth(sensorId, true);
    } catch (error) {
        console.error(`Error polling sensor ${sensorId}:`, error.message);
        updateSensorHealth(sensorId, false, error.message);
    }
}

/**
 * Main polling loop
 *
 * Continuously polls all registered sensors at the configured interval.
 * Uses setInterval to ensure consistent polling regardless of response times.
 */
function startPolling() {
    // In production, sensor list would come from configuration
    // For this example, we create some default sensors
    const defaultSensors = ['motion_front_door', 'motion_hallway', 'motion_garage'];

    defaultSensors.forEach(sensorId => {
        if (!sensorStates.has(sensorId)) {
            sensorStates.set(sensorId, {
                sensor_id: sensorId,
                motion_detected: false,
                timestamp: new Date().toISOString()
            });
        }
    });

    // Poll all sensors at regular interval
    setInterval(async () => {
        const pollPromises = Array.from(sensorStates.keys()).map(pollSensor);
        await Promise.allSettled(pollPromises);
    }, POLL_INTERVAL);

    console.log(`Started polling ${sensorStates.size} motion sensors every ${POLL_INTERVAL}ms`);
}

// REST API endpoints

/**
 * Health check endpoint
 */
app.get('/health', (req, res) => {
    const healthySensors = Array.from(sensorHealth.values()).filter(h => h.status === 'online').length;
    const totalSensors = sensorHealth.size;

    res.json({
        service: 'http-poller',
        status: healthySensors > 0 ? 'healthy' : 'degraded',
        timestamp: new Date().toISOString(),
        sensors_total: totalSensors,
        sensors_online: healthySensors,
        poll_interval: POLL_INTERVAL
    });
});

/**
 * List all sensors being polled
 */
app.get('/sensors', (req, res) => {
    const sensors = Array.from(sensorStates.keys()).map(sensorId => {
        const state = sensorStates.get(sensorId);
        const health = sensorHealth.get(sensorId);
        return {
            sensor_id: sensorId,
            type: 'motion',
            motion_detected: state.motion_detected,
            last_update: state.timestamp,
            status: health?.status || 'unknown'
        };
    });

    res.json({
        sensors,
        count: sensors.length
    });
});

/**
 * Get current state of a specific sensor
 */
app.get('/sensor/:sensorId', (req, res) => {
    const { sensorId } = req.params;

    if (!sensorStates.has(sensorId)) {
        return res.status(404).json({
            error: 'UNKNOWN_SENSOR',
            message: `Sensor ${sensorId} not configured`
        });
    }

    const state = sensorStates.get(sensorId);
    const health = sensorHealth.get(sensorId);
    const error = sensorErrors.get(sensorId);

    // If sensor is offline, return error status
    if (health?.status === 'offline' || health?.status === 'degraded') {
        return res.status(503).json({
            error: 'SENSOR_UNAVAILABLE',
            message: error?.message || 'Sensor is not responding',
            sensor_id: sensorId,
            status: health.status,
            last_success: health.last_success
        });
    }

    res.json(state);
});

/**
 * Get health information for a specific sensor
 */
app.get('/sensor/:sensorId/health', (req, res) => {
    const { sensorId } = req.params;

    if (!sensorHealth.has(sensorId)) {
        return res.status(404).json({
            error: 'UNKNOWN_SENSOR',
            message: `Sensor ${sensorId} not configured`
        });
    }

    res.json(sensorHealth.get(sensorId));
});

/**
 * Get all current errors
 */
app.get('/errors', (req, res) => {
    const errors = {};
    sensorErrors.forEach((error, sensorId) => {
        errors[sensorId] = error;
    });

    res.json({
        errors,
        count: sensorErrors.size,
        timestamp: new Date().toISOString()
    });
});

// Start the service
function startService() {
    // Start polling loop
    startPolling();

    // Start HTTP server
    app.listen(SERVICE_PORT, '0.0.0.0', () => {
        console.log(`HTTP Poller Service listening on port ${SERVICE_PORT}`);
        console.log('This service polls network-connected motion sensors');
        console.log(`Health check: http://localhost:${SERVICE_PORT}/health`);
    });
}

// Error handling for uncaught exceptions
process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception:', error);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// Start the service
startService();
