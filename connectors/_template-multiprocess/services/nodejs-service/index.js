#!/usr/bin/env node
/**
 * Node.js Backend Service - Example HTTP API
 *
 * This service demonstrates integrating Node.js processes in a multi-language
 * connector. It exposes a simple HTTP REST API that the MQTT bridge calls.
 *
 * In a real connector, Node.js services are useful for:
 * - Real-time streaming (WebSocket, Server-Sent Events)
 * - High-performance I/O operations
 * - Integration with Node.js-specific libraries
 * - Video/audio processing pipelines
 */

const express = require('express');

// Service configuration from environment
const PORT = process.env.PORT || 5002;
const NODE_ENV = process.env.NODE_ENV || 'production';

// Create Express application
const app = express();

// Middleware
app.use(express.json());

// Request logging middleware
app.use((req, res, next) => {
    console.log(`${new Date().toISOString()} - ${req.method} ${req.path}`);
    next();
});

// Internal state (in real connector, this would track device/stream state)
const serviceState = {
    status: 'running',
    startedAt: new Date().toISOString(),
    requestCount: 0,
    lastCommand: null
};

/**
 * Health check endpoint
 * Used by MQTT bridge to verify service is running
 */
app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        service: 'nodejs-service',
        timestamp: new Date().toISOString()
    });
});

/**
 * Get current service status
 * Called by MQTT bridge during polling to gather device state
 *
 * In a real connector, this would:
 * - Check streaming connections
 * - Monitor buffer health
 * - Return processing statistics
 */
app.post('/status', (req, res) => {
    serviceState.requestCount++;

    res.json({
        status: serviceState.status,
        startedAt: serviceState.startedAt,
        requestCount: serviceState.requestCount,
        lastCommand: serviceState.lastCommand,
        timestamp: new Date().toISOString()
    });
});

/**
 * Execute a command
 * Called by MQTT bridge when MQTT commands are received
 *
 * In a real connector, this would:
 * - Control streaming parameters
 * - Adjust processing settings
 * - Manage connections
 */
app.post('/command', (req, res) => {
    try {
        const data = req.body || {};
        console.log('Received command:', JSON.stringify(data));

        // Store last command
        serviceState.lastCommand = {
            data: data,
            timestamp: new Date().toISOString()
        };

        // Simulate command processing
        // In real connector: adjust stream settings, update configuration, etc.

        res.json({
            success: true,
            message: 'Command processed successfully',
            command: data,
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        console.error('Error processing command:', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

/**
 * Reset service state (example of service-specific endpoint)
 */
app.post('/reset', (req, res) => {
    serviceState.requestCount = 0;
    serviceState.lastCommand = null;

    console.log('Service state reset');

    res.json({
        success: true,
        message: 'Service state reset'
    });
});

/**
 * Example: Stream endpoint (demonstrates Node.js streaming capability)
 * In real connector, this could be:
 * - WebSocket for real-time data
 * - Server-Sent Events for push updates
 * - Chunked transfer for large data
 */
app.get('/stream', (req, res) => {
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');

    // Send periodic updates
    const intervalId = setInterval(() => {
        const data = {
            timestamp: new Date().toISOString(),
            value: Math.random() * 100
        };

        res.write(`data: ${JSON.stringify(data)}\n\n`);
    }, 1000);

    // Clean up on client disconnect
    req.on('close', () => {
        clearInterval(intervalId);
        console.log('Stream client disconnected');
    });
});

// Error handling middleware
app.use((err, req, res, next) => {
    console.error('Unhandled error:', err);
    res.status(500).json({
        error: 'Internal server error',
        message: err.message
    });
});

// Start server
const server = app.listen(PORT, '0.0.0.0', () => {
    console.log('='.repeat(60));
    console.log('Node.js Backend Service Starting');
    console.log('='.repeat(60));
    console.log(`Port: ${PORT}`);
    console.log(`Environment: ${NODE_ENV}`);
    console.log(`Process ID: ${process.pid}`);
});

// Graceful shutdown handling
process.on('SIGTERM', () => {
    console.log('SIGTERM received, shutting down gracefully...');
    server.close(() => {
        console.log('Server closed');
        process.exit(0);
    });
});

process.on('SIGINT', () => {
    console.log('SIGINT received, shutting down gracefully...');
    server.close(() => {
        console.log('Server closed');
        process.exit(0);
    });
});
