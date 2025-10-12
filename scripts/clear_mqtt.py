#!/usr/bin/env python3
"""
Clear all IoT2MQTT topics from MQTT broker
This script removes ALL retained messages for IoT2MQTT topics
"""

import os
import sys
import json
import time
import paho.mqtt.client as mqtt
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def load_mqtt_config():
    """Load MQTT configuration from .env file"""
    config_file = Path('.env')
    if not config_file.exists():
        print("Error: .env file not found")
        sys.exit(1)
    
    # Parse .env file
    config = {}
    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip().strip('"').strip("'")
    
    return {
        'host': config.get('MQTT_HOST', 'localhost'),
        'port': int(config.get('MQTT_PORT', 1883)),
        'username': config.get('MQTT_USERNAME', ''),
        'password': config.get('MQTT_PASSWORD', ''),
        'base_topic': config.get('MQTT_BASE_TOPIC', 'IoT2mqtt')
    }

def clear_all_topics(config):
    """Clear all IoT2MQTT topics from broker"""
    
    print(f"Connecting to MQTT broker at {config['host']}:{config['port']}")
    
    # Track found topics
    topics_to_clear = []
    connected = False
    
    def on_connect(client, userdata, flags, rc):
        nonlocal connected
        if rc == 0:
            print("✓ Connected to MQTT broker")
            connected = True
            # Subscribe to all IoT2MQTT topics
            base_topic = config['base_topic']
            client.subscribe(f"{base_topic}/#")
            print(f"Scanning for topics under {base_topic}/...")
        else:
            print(f"✗ Connection failed with code {rc}")
    
    def on_message(client, userdata, msg):
        # Collect topics with retained messages
        if msg.retain:
            topics_to_clear.append(msg.topic)
            print(f"  Found: {msg.topic}")
    
    # Create MQTT client
    client = mqtt.Client(client_id="iot2mqtt_cleaner")
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Set authentication if configured
    if config['username'] and config['password']:
        client.username_pw_set(config['username'], config['password'])
    
    # Connect
    try:
        client.connect(config['host'], config['port'], keepalive=60)
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        return False
    
    # Start loop
    client.loop_start()
    
    # Wait for connection
    timeout = 10
    while not connected and timeout > 0:
        time.sleep(0.1)
        timeout -= 0.1
    
    if not connected:
        print("✗ Connection timeout")
        client.loop_stop()
        return False
    
    # Wait to collect all topics
    print("Scanning for topics (3 seconds)...")
    time.sleep(3)
    
    # Now clear all found topics
    if topics_to_clear:
        print(f"\nFound {len(topics_to_clear)} topics to clear")
        print("Clearing topics...")
        
        for topic in topics_to_clear:
            # Publish empty retained message to clear
            client.publish(topic, "", retain=True, qos=0)
            print(f"  Cleared: {topic}")
        
        # Wait for messages to be sent
        time.sleep(1)
        print(f"\n✓ Successfully cleared {len(topics_to_clear)} topics")
    else:
        print("\n✓ No IoT2MQTT topics found in broker")
    
    # Disconnect
    client.loop_stop()
    client.disconnect()
    
    return True

def main():
    """Main function"""
    print("=" * 60)
    print("IoT2MQTT - MQTT Topic Cleaner")
    print("=" * 60)
    print("\n⚠️  WARNING: This will DELETE all IoT2MQTT data from MQTT!")
    print("This action cannot be undone.\n")
    
    # Ask for confirmation
    response = input("Are you sure you want to continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        return
    
    # Load configuration
    config = load_mqtt_config()
    
    # Clear topics
    success = clear_all_topics(config)
    
    if success:
        print("\n✓ MQTT cleanup completed successfully")
    else:
        print("\n✗ MQTT cleanup failed")
        sys.exit(1)

if __name__ == "__main__":
    main()