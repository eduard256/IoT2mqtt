#!/usr/bin/env python3
"""
Test script for new MQTT command standard
"""
import paho.mqtt.client as mqtt
import json
import time
import sys

# MQTT settings
MQTT_HOST = "10.0.20.104"
MQTT_PORT = 1883
BASE_TOPIC = "IoT2mqtt/v1"
INSTANCE_ID = "yeelight_10_0_20_44_1757601161485"
DEVICE_ID = "yeelight_10_0_20_44"

def send_command(client, values, cmd_id=None):
    """Send command to device"""
    topic = f"{BASE_TOPIC}/instances/{INSTANCE_ID}/devices/{DEVICE_ID}/cmd"
    
    payload = {
        "values": values,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    }
    
    if cmd_id:
        payload["id"] = cmd_id
    
    print(f"Sending to {topic}:")
    print(f"  {json.dumps(values, indent=2)}")
    
    client.publish(topic, json.dumps(payload))
    time.sleep(2)  # Wait for response

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")
    # Subscribe to response topic
    response_topic = f"{BASE_TOPIC}/instances/{INSTANCE_ID}/devices/{DEVICE_ID}/cmd/response"
    client.subscribe(response_topic)
    print(f"Subscribed to {response_topic}")

def on_message(client, userdata, msg):
    print(f"Response: {msg.topic}")
    try:
        payload = json.loads(msg.payload.decode())
        print(f"  {json.dumps(payload, indent=2)}")
    except:
        print(f"  {msg.payload.decode()}")

def main():
    # Create MQTT client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Connect
    print(f"Connecting to {MQTT_HOST}:{MQTT_PORT}")
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()
    
    time.sleep(2)  # Wait for connection
    
    print("\n=== Testing New Command Standard ===\n")
    
    # Test 1: Power on
    print("1. Power ON")
    send_command(client, {"power": True})
    
    # Test 2: Power toggle
    print("2. Power TOGGLE")
    send_command(client, {"power": "toggle"})
    
    time.sleep(1)
    
    # Test 3: Power toggle again
    print("3. Power TOGGLE (turn on)")
    send_command(client, {"power": "toggle"})
    
    # Test 4: Color with HEX
    print("4. Color HEX (Red)")
    send_command(client, {"color": "#FF0000"})
    
    # Test 5: Color with RGB
    print("5. Color RGB (Blue)")
    send_command(client, {"color": {"r": 0, "g": 0, "b": 255}})
    
    # Test 6: Color with HSV
    print("6. Color HSV (Green)")
    send_command(client, {"color": {"h": 120, "s": 100, "v": 100}})
    
    # Test 7: Brightness with relative change
    print("7. Brightness +20")
    send_command(client, {"brightness": "+20"})
    
    # Test 8: Brightness with relative change negative
    print("8. Brightness -10")
    send_command(client, {"brightness": "-10"})
    
    # Test 9: Brightness step
    print("9. Brightness step +15")
    send_command(client, {"brightness_step": 15})
    
    # Test 10: With transition
    print("10. Brightness 100 with 3s transition")
    send_command(client, {"brightness": 100, "transition": 3000})
    
    time.sleep(4)  # Wait for transition
    
    # Test 11: Multiple values with transition
    print("11. Color and brightness with transition")
    send_command(client, {"color": "#FFA500", "brightness": 50, "transition": 2000})
    
    time.sleep(3)
    
    # Test 12: Color temperature
    print("12. Color temperature 4000K")
    send_command(client, {"color_temp": 4000})
    
    # Test 13: Color temperature relative
    print("13. Color temperature +500")
    send_command(client, {"color_temp": "+500"})
    
    print("\n=== All tests completed ===")
    
    # Cleanup
    time.sleep(2)
    client.loop_stop()
    client.disconnect()

if __name__ == "__main__":
    main()