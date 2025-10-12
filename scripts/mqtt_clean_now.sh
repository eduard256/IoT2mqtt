#!/bin/bash

# Load MQTT config from .env
source .env

echo "Clearing all IoT2MQTT topics from MQTT broker..."

# Connect to MQTT and clear all retained messages for IoT2MQTT topics
# We need to publish empty retained messages to remove them

# Get all topics (using mosquitto_sub to list them first)
echo "Scanning for IoT2MQTT topics..."

# Subscribe to all IoT2MQTT topics for 3 seconds to get the list
timeout 3 mosquitto_sub -h "$MQTT_HOST" -p "$MQTT_PORT" \
    ${MQTT_USERNAME:+-u "$MQTT_USERNAME"} \
    ${MQTT_PASSWORD:+-P "$MQTT_PASSWORD"} \
    -t "${MQTT_BASE_TOPIC:-IoT2mqtt}/#" -v --retained-only | \
    cut -d' ' -f1 > /tmp/mqtt_topics.txt

# Check if we found any topics
if [ ! -s /tmp/mqtt_topics.txt ]; then
    echo "No IoT2MQTT topics found in broker"
    exit 0
fi

# Count topics
TOPIC_COUNT=$(wc -l < /tmp/mqtt_topics.txt)
echo "Found $TOPIC_COUNT topics to clear"

# Clear each topic
while IFS= read -r topic; do
    echo "Clearing: $topic"
    mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" \
        ${MQTT_USERNAME:+-u "$MQTT_USERNAME"} \
        ${MQTT_PASSWORD:+-P "$MQTT_PASSWORD"} \
        -t "$topic" -r -n
done < /tmp/mqtt_topics.txt

# Clean up
rm -f /tmp/mqtt_topics.txt

echo "✓ MQTT cleanup completed - cleared $TOPIC_COUNT topics"