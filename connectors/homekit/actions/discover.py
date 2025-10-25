#!/usr/bin/env python3
"""
HomeKit Device Discovery
Scans local network for HomeKit devices using mDNS/DNS-SD
"""

import json
import sys
import asyncio
import logging
from typing import List, Dict, Any

try:
    from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf
    from zeroconf.asyncio import AsyncZeroconf, AsyncServiceBrowser
except ImportError:
    print(json.dumps({
        "ok": False,
        "error": {
            "code": "missing_dependency",
            "message": "zeroconf package is not installed",
            "retriable": False
        }
    }))
    sys.exit(0)

# Disable logging for clean JSON output
logging.disable(logging.CRITICAL)


class HomeKitDiscovery:
    """HomeKit device discovery using mDNS"""

    # HomeKit service types
    SERVICE_TYPES = [
        "_hap._tcp.local.",  # IP/WiFi devices
        "_hap._udp.local.",  # CoAP/Thread devices
    ]

    # Categories mapping (from HAP spec)
    CATEGORIES = {
        1: "Other",
        2: "Bridge",
        3: "Fan",
        4: "Garage Door Opener",
        5: "Lightbulb",
        6: "Door Lock",
        7: "Outlet",
        8: "Switch",
        9: "Thermostat",
        10: "Sensor",
        11: "Security System",
        12: "Door",
        13: "Window",
        14: "Window Covering",
        15: "Programmable Switch",
        16: "Range Extender",
        17: "IP Camera",
        18: "Video Doorbell",
        19: "Air Purifier",
        20: "Heater",
        21: "Air Conditioner",
        22: "Humidifier",
        23: "Dehumidifier",
        28: "Sprinkler",
        29: "Faucet",
        30: "Shower System",
        31: "Television",
        32: "Target Remote",
        33: "Router",
        34: "Audio Receiver",
        35: "TV Set Top Box",
        36: "TV Streaming Stick"
    }

    # Known problematic devices to ignore
    IGNORED_MODELS = [
        "T8400",  # eufy HomeBase 2
        "T8410",  # eufy cameras (better native integration exists)
        "HHKBridge1,1",  # Hive hub (no pairing code support)
    ]

    def __init__(self, timeout: int = 10):
        """
        Initialize discovery

        Args:
            timeout: Discovery timeout in seconds
        """
        self.timeout = timeout
        self.devices = []
        self.seen_ids = set()

    def parse_txt_record(self, properties: Dict[bytes, bytes]) -> Dict[str, Any]:
        """
        Parse HomeKit TXT record from mDNS

        Args:
            properties: TXT record properties

        Returns:
            Parsed properties dictionary
        """
        parsed = {}

        # Decode all properties
        for key, value in properties.items():
            try:
                key_str = key.decode('utf-8')
                value_str = value.decode('utf-8') if value else ''
                parsed[key_str] = value_str
            except Exception:
                continue

        return parsed

    def process_device(self, name: str, address: str, port: int,
                      properties: Dict[str, Any], transport: str):
        """
        Process discovered HomeKit device

        Args:
            name: Service name
            address: IP address
            port: Port number
            properties: Parsed TXT record
            transport: Transport type (IP or CoAP)
        """
        try:
            # Extract key properties
            device_id = properties.get('id', '')  # Device ID (MAC-like)
            model = properties.get('md', 'Unknown')  # Model
            protocol_version = properties.get('pv', '1.0')  # Protocol version
            config_num = properties.get('c#', '1')  # Configuration number
            state_num = properties.get('s#', '1')  # State number
            status_flags = int(properties.get('sf', '0'))  # Status flags
            category = int(properties.get('ci', '1'))  # Category identifier
            feature_flags = properties.get('ff', '0')  # Feature flags

            # Check if device is ignored
            if model in self.IGNORED_MODELS:
                return

            # Check if already seen
            if device_id in self.seen_ids:
                return

            self.seen_ids.add(device_id)

            # Status flags bits:
            # bit 0: Not paired (0 = paired, 1 = not paired)
            # bit 1: Not configured for WiFi
            # bit 2: Problem detected
            paired = not bool(status_flags & 0x01)
            has_problem = bool(status_flags & 0x04)

            # Get category name
            category_name = self.CATEGORIES.get(category, "Other")

            # Build device info
            device = {
                "device_id": device_id or address.replace('.', '_'),
                "name": name.split('.')[0],  # Remove .local suffix
                "ip": address,
                "port": port,
                "model": model,
                "category": category_name,
                "category_id": category,
                "protocol_version": protocol_version,
                "config_num": config_num,
                "state_num": state_num,
                "status_flags": status_flags,
                "feature_flags": feature_flags,
                "paired": paired,
                "has_problem": has_problem,
                "transport": transport,
                "integration": "homekit",
                "manufacturer": "Apple HomeKit"
            }

            self.devices.append(device)

        except Exception as e:
            # Silently skip problematic devices
            pass

    async def discover_async(self) -> List[Dict[str, Any]]:
        """
        Perform async mDNS discovery

        Returns:
            List of discovered devices
        """
        aiozc = AsyncZeroconf()

        try:
            services_discovered = []

            def on_service_state_change(
                zeroconf: Zeroconf,
                service_type: str,
                name: str,
                state_change: ServiceStateChange
            ):
                """Callback for service state changes"""
                if state_change == ServiceStateChange.Added:
                    info = zeroconf.get_service_info(service_type, name)
                    if info:
                        services_discovered.append((service_type, info))

            # Browse for both service types
            browsers = []
            for service_type in self.SERVICE_TYPES:
                browser = AsyncServiceBrowser(
                    aiozc.zeroconf,
                    service_type,
                    handlers=[on_service_state_change]
                )
                browsers.append(browser)

            # Wait for discovery timeout
            await asyncio.sleep(self.timeout)

            # Process discovered services
            for service_type, info in services_discovered:
                try:
                    # Get addresses
                    addresses = info.parsed_addresses()
                    if not addresses:
                        continue

                    address = addresses[0]  # Use first IPv4 address

                    # Parse TXT record
                    properties = self.parse_txt_record(info.properties)

                    # Determine transport
                    transport = "CoAP" if "_udp" in service_type else "IP"

                    # Process device
                    self.process_device(
                        name=info.name,
                        address=address,
                        port=info.port,
                        properties=properties,
                        transport=transport
                    )

                except Exception:
                    continue

            # Cancel browsers
            for browser in browsers:
                await browser.async_cancel()

        finally:
            await aiozc.async_close()

        return self.devices


async def discover_devices(timeout: int = 10) -> Dict[str, Any]:
    """
    Discover HomeKit devices

    Args:
        timeout: Discovery timeout in seconds

    Returns:
        Discovery result with devices list
    """
    try:
        discovery = HomeKitDiscovery(timeout=timeout)
        devices = await discovery.discover_async()

        return {
            "ok": True,
            "result": {
                "count": len(devices),
                "devices": devices
            }
        }

    except Exception as e:
        return {
            "ok": False,
            "error": {
                "code": "discovery_failed",
                "message": str(e),
                "retriable": True
            }
        }


def main():
    """Main entry point"""
    # Get timeout from command line or use default
    timeout = int(sys.argv[1]) if len(sys.argv) > 1 else 10

    # Run discovery
    result = asyncio.run(discover_devices(timeout))

    # Output JSON
    print(json.dumps(result))


if __name__ == "__main__":
    main()
