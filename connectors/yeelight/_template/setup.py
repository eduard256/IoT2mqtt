#!/usr/bin/env python3
"""
Template Connector - Setup wizard
Interactive CLI for creating a new instance configuration
"""

import os
import sys
import json
import getpass
from pathlib import Path
from typing import Dict, Any, List, Optional
import socket

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.columns import Columns
from rich import box
from rich.text import Text

console = Console()

class ConnectorSetup:
    """Interactive setup wizard for Template Connector"""
    
    def __init__(self):
        self.config = {
            "instance_id": "",
            "instance_type": "device",  # device, account, service
            "connector_type": "template",
            "friendly_name": "",
            "connection": {},
            "devices": [],
            "groups": [],
            "mqtt": {
                "qos": 1,
                "retain_state": True,
                "telemetry_mode": "individual",
                "telemetry_interval": 60000
            },
            "update_interval": 10,
            "error_handling": {
                "max_retries": 3,
                "retry_interval": 5000,
                "backoff_multiplier": 2
            },
            "discovery": {
                "enabled": False
            }
        }
        
        self.instances_dir = Path(__file__).parent / "instances"
        self.instances_dir.mkdir(exist_ok=True)
    
    def show_welcome(self):
        """Show welcome screen"""
        console.clear()
        
        # Template-specific ASCII art or logo
        logo = """
        ╔╦╗╔═╗╔╦╗╔═╗╦  ╔═╗╔╦╗╔═╗
         ║ ║╣ ║║║╠═╝║  ╠═╣ ║ ║╣ 
         ╩ ╚═╝╩ ╩╩  ╩═╝╩ ╩ ╩ ╚═╝
        """
        
        console.print(Panel.fit(
            f"[bold cyan]{logo}[/bold cyan]\n\n"
            "[bold]Template Connector Setup Wizard[/bold]\n"
            "[dim]This wizard will help you configure a new instance[/dim]",
            border_style="cyan",
            box=box.DOUBLE
        ))
        
        console.print("\n[yellow]This is a template connector.[/yellow]")
        console.print("You should customize this setup script for your specific device/service.\n")
    
    def configure_instance(self):
        """Configure basic instance settings"""
        console.print(Panel.fit(
            "[bold cyan]Step 1: Instance Configuration[/bold cyan]",
            border_style="cyan"
        ))
        
        # Instance name
        console.print("\n[bold]Instance Name[/bold]")
        console.print("[dim]Unique identifier for this instance (e.g., 'home_devices', 'office_sensors')[/dim]")
        
        while True:
            instance_name = Prompt.ask("  Instance name").lower().replace(' ', '_')
            
            # Validate instance name
            if not instance_name or not instance_name.replace('_', '').replace('-', '').isalnum():
                console.print("[red]Invalid instance name! Use only letters, numbers, and underscores.[/red]")
                continue
            
            # Check if already exists
            config_file = self.instances_dir / f"{instance_name}.json"
            if config_file.exists():
                if not Confirm.ask(f"  [yellow]Instance '{instance_name}' already exists. Overwrite?[/yellow]"):
                    continue
            
            self.config["instance_id"] = instance_name
            break
        
        # Friendly name
        console.print("\n[bold]Friendly Name[/bold]")
        console.print("[dim]Human-readable name for this instance[/dim]")
        
        self.config["friendly_name"] = Prompt.ask(
            "  Friendly name",
            default=instance_name.replace('_', ' ').title()
        )
        
        # Instance type
        console.print("\n[bold]Instance Type[/bold]")
        console.print("[dim]What type of connection is this?[/dim]")
        console.print("  [1] Individual devices (local network)")
        console.print("  [2] Cloud account (multiple devices)")
        console.print("  [3] Service integration (API)")
        
        choice = IntPrompt.ask("  Your choice", choices=["1", "2", "3"], default=1)
        self.config["instance_type"] = ["device", "account", "service"][choice - 1]
    
    def configure_connection(self):
        """Configure connection settings"""
        console.print("\n")
        console.print(Panel.fit(
            "[bold cyan]Step 2: Connection Settings[/bold cyan]",
            border_style="cyan"
        ))
        
        # === CUSTOMIZE THIS SECTION FOR YOUR CONNECTOR ===
        
        # Example for local device connection
        if self.config["instance_type"] == "device":
            console.print("\n[bold]Device Connection[/bold]")
            
            # IP Address
            self.config["connection"]["host"] = Prompt.ask(
                "  Device IP address",
                default="192.168.1.100"
            )
            
            # Port
            self.config["connection"]["port"] = IntPrompt.ask(
                "  Device port",
                default=80
            )
            
            # Authentication
            if Confirm.ask("  Does the device require authentication?", default=False):
                self.config["connection"]["username"] = Prompt.ask("    Username")
                self.config["connection"]["password"] = getpass.getpass("    Password: ")
        
        # Example for cloud account
        elif self.config["instance_type"] == "account":
            console.print("\n[bold]Account Settings[/bold]")
            
            # Server/Region
            console.print("\n[bold]Server Region[/bold]")
            console.print("[dim]Select your account region[/dim]")
            servers = ["us", "eu", "cn", "au"]
            for i, server in enumerate(servers, 1):
                console.print(f"  [{i}] {server.upper()}")
            
            choice = IntPrompt.ask("  Your choice", default=1, choices=list(map(str, range(1, len(servers)+1))))
            self.config["connection"]["server"] = servers[choice - 1]
            
            # Credentials
            console.print("\n[bold]Account Credentials[/bold]")
            self.config["connection"]["email"] = Prompt.ask("  Email/Username")
            self.config["connection"]["password"] = getpass.getpass("  Password: ")
            
            # 2FA
            if Confirm.ask("  Does your account have 2FA enabled?", default=False):
                self.config["connection"]["requires_2fa"] = True
                console.print("[yellow]  Note: You'll need to provide 2FA code when the connector starts[/yellow]")
        
        # Example for API service
        elif self.config["instance_type"] == "service":
            console.print("\n[bold]API Configuration[/bold]")
            
            # API Endpoint
            self.config["connection"]["api_url"] = Prompt.ask(
                "  API endpoint URL",
                default="https://api.example.com/v1"
            )
            
            # API Key
            self.config["connection"]["api_key"] = getpass.getpass("  API Key: ")
            
            # Additional headers
            if Confirm.ask("  Add custom headers?", default=False):
                headers = {}
                while True:
                    header_name = Prompt.ask("    Header name (empty to finish)")
                    if not header_name:
                        break
                    header_value = Prompt.ask(f"    {header_name} value")
                    headers[header_name] = header_value
                
                self.config["connection"]["headers"] = headers
    
    def discover_devices(self):
        """Discover and configure devices"""
        console.print("\n")
        console.print(Panel.fit(
            "[bold cyan]Step 3: Device Discovery[/bold cyan]",
            border_style="cyan"
        ))
        
        # === CUSTOMIZE THIS SECTION FOR YOUR CONNECTOR ===
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("[yellow]Searching for devices...[/yellow]", total=None)
            
            # Simulate device discovery
            import time
            time.sleep(2)  # Replace with actual discovery
            
            # Example discovered devices
            discovered = [
                {
                    "id": "device_1",
                    "name": "Living Room Light",
                    "model": "Generic Smart Bulb",
                    "ip": "192.168.1.101",
                    "capabilities": {
                        "power": {"settable": True},
                        "brightness": {"settable": True, "min": 0, "max": 100}
                    }
                },
                {
                    "id": "device_2",
                    "name": "Temperature Sensor",
                    "model": "Generic Sensor",
                    "ip": "192.168.1.102",
                    "capabilities": {
                        "temperature": {"settable": False},
                        "humidity": {"settable": False}
                    }
                }
            ]
            
            progress.update(task, completed=True)
        
        if not discovered:
            console.print("[yellow]No devices discovered.[/yellow]")
            
            if Confirm.ask("Would you like to add devices manually?", default=True):
                discovered = self.manual_device_config()
        else:
            console.print(f"\n[green]Found {len(discovered)} device(s)![/green]\n")
            
            # Show discovered devices
            table = Table(title="Discovered Devices", box=box.ROUNDED)
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Model")
            table.add_column("IP")
            
            for device in discovered:
                table.add_row(
                    device["id"],
                    device["name"],
                    device["model"],
                    device.get("ip", "N/A")
                )
            
            console.print(table)
            
            # Select devices to add
            console.print("\n[bold]Select devices to add[/bold]")
            console.print("[dim]Enter device IDs separated by commas, or 'all' for all devices[/dim]")
            
            selection = Prompt.ask("  Devices to add", default="all")
            
            if selection.lower() == "all":
                selected_devices = discovered
            else:
                selected_ids = [s.strip() for s in selection.split(",")]
                selected_devices = [d for d in discovered if d["id"] in selected_ids]
        
        # Configure each selected device
        for device in selected_devices:
            console.print(f"\n[bold]Configuring {device['name']}[/bold]")
            
            # Custom device ID
            device_id = Prompt.ask(
                "  Device ID",
                default=device["id"]
            )
            
            # Friendly name
            friendly_name = Prompt.ask(
                "  Friendly name",
                default=device["name"]
            )
            
            # Area/Room
            area = Prompt.ask(
                "  Area/Room",
                default=""
            )
            
            # Add to config
            device_config = {
                "device_id": device_id,
                "global_id": f"{self.config['instance_id']}_{device_id}",
                "friendly_name": friendly_name,
                "model": device.get("model", "Unknown"),
                "enabled": True,
                "capabilities": device.get("capabilities", {})
            }
            
            if area:
                device_config["area"] = area
            
            # Add device-specific connection info
            if "ip" in device:
                device_config["ip"] = device["ip"]
            if "mac" in device:
                device_config["mac"] = device["mac"]
            
            self.config["devices"].append(device_config)
        
        console.print(f"\n[green]Added {len(self.config['devices'])} device(s) to configuration[/green]")
    
    def manual_device_config(self) -> List[Dict[str, Any]]:
        """Manual device configuration"""
        devices = []
        
        while True:
            console.print("\n[bold]Add Device Manually[/bold]")
            
            device = {
                "id": Prompt.ask("  Device ID"),
                "name": Prompt.ask("  Device name"),
                "model": Prompt.ask("  Device model", default="Generic Device"),
                "ip": Prompt.ask("  Device IP (optional)", default="")
            }
            
            # Basic capabilities
            device["capabilities"] = {}
            
            if Confirm.ask("  Can control power?", default=True):
                device["capabilities"]["power"] = {"settable": True}
            
            if Confirm.ask("  Has temperature sensor?", default=False):
                device["capabilities"]["temperature"] = {"settable": False}
            
            if Confirm.ask("  Has humidity sensor?", default=False):
                device["capabilities"]["humidity"] = {"settable": False}
            
            devices.append(device)
            
            if not Confirm.ask("\nAdd another device?", default=False):
                break
        
        return devices
    
    def configure_groups(self):
        """Configure device groups"""
        if len(self.config["devices"]) < 2:
            return
        
        console.print("\n")
        console.print(Panel.fit(
            "[bold cyan]Step 4: Device Groups (Optional)[/bold cyan]",
            border_style="cyan"
        ))
        
        if not Confirm.ask("\nWould you like to create device groups?", default=False):
            return
        
        while True:
            console.print("\n[bold]Create Group[/bold]")
            
            group_id = Prompt.ask("  Group ID").lower().replace(' ', '_')
            group_name = Prompt.ask("  Group name", default=group_id.replace('_', ' ').title())
            
            # Show available devices
            console.print("\n[bold]Available devices:[/bold]")
            for i, device in enumerate(self.config["devices"], 1):
                console.print(f"  [{i}] {device['friendly_name']} ({device['device_id']})")
            
            # Select devices for group
            selection = Prompt.ask("  Select devices (comma-separated numbers)")
            indices = [int(s.strip()) - 1 for s in selection.split(",")]
            
            group_devices = []
            for i in indices:
                if 0 <= i < len(self.config["devices"]):
                    group_devices.append(self.config["devices"][i]["device_id"])
            
            if group_devices:
                self.config["groups"].append({
                    "group_id": group_id,
                    "name": group_name,
                    "devices": group_devices
                })
                console.print(f"[green]Created group '{group_name}' with {len(group_devices)} devices[/green]")
            
            if not Confirm.ask("\nCreate another group?", default=False):
                break
    
    def configure_advanced(self):
        """Configure advanced settings"""
        console.print("\n")
        console.print(Panel.fit(
            "[bold cyan]Step 5: Advanced Settings (Optional)[/bold cyan]",
            border_style="cyan"
        ))
        
        if not Confirm.ask("\nConfigure advanced settings?", default=False):
            return
        
        # Update interval
        console.print("\n[bold]Update Interval[/bold]")
        console.print("[dim]How often to poll devices for updates (in seconds)[/dim]")
        
        self.config["update_interval"] = IntPrompt.ask(
            "  Update interval",
            default=10,
            min_value=1,
            max_value=3600
        )
        
        # Telemetry mode
        console.print("\n[bold]Telemetry Mode[/bold]")
        console.print("[dim]How to send telemetry data[/dim]")
        console.print("  [1] Individual (each device separately)")
        console.print("  [2] Batch (all devices together)")
        
        choice = IntPrompt.ask("  Your choice", choices=["1", "2"], default=1)
        self.config["mqtt"]["telemetry_mode"] = ["individual", "batch"][choice - 1]
        
        # Home Assistant Discovery
        console.print("\n[bold]Home Assistant Discovery[/bold]")
        console.print("[dim]Enable automatic discovery in Home Assistant[/dim]")
        
        self.config["discovery"]["enabled"] = Confirm.ask(
            "  Enable HA discovery?",
            default=False
        )
        
        # Error handling
        console.print("\n[bold]Error Handling[/bold]")
        
        self.config["error_handling"]["max_retries"] = IntPrompt.ask(
            "  Max retry attempts",
            default=3
        )
        
        self.config["error_handling"]["retry_interval"] = IntPrompt.ask(
            "  Retry interval (ms)",
            default=5000
        )
    
    def show_summary(self):
        """Show configuration summary"""
        console.print("\n")
        console.print(Panel.fit(
            "[bold cyan]Configuration Summary[/bold cyan]",
            border_style="cyan"
        ))
        
        # Basic info
        info_table = Table(show_header=False, box=None)
        info_table.add_column("Property", style="cyan")
        info_table.add_column("Value", style="green")
        
        info_table.add_row("Instance ID", self.config["instance_id"])
        info_table.add_row("Friendly Name", self.config["friendly_name"])
        info_table.add_row("Instance Type", self.config["instance_type"])
        info_table.add_row("Devices", str(len(self.config["devices"])))
        info_table.add_row("Groups", str(len(self.config["groups"])))
        info_table.add_row("Update Interval", f"{self.config['update_interval']}s")
        
        console.print(info_table)
        
        # Devices
        if self.config["devices"]:
            console.print("\n[bold]Configured Devices:[/bold]")
            for device in self.config["devices"]:
                status = "[green]✓[/green]" if device["enabled"] else "[red]✗[/red]"
                console.print(f"  {status} {device['friendly_name']} ({device['device_id']})")
        
        # Groups
        if self.config["groups"]:
            console.print("\n[bold]Device Groups:[/bold]")
            for group in self.config["groups"]:
                console.print(f"  • {group['name']} ({len(group['devices'])} devices)")
    
    def save_configuration(self):
        """Save configuration to file"""
        config_file = self.instances_dir / f"{self.config['instance_id']}.json"
        
        with open(config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
        
        console.print(f"\n[green]✓ Configuration saved to {config_file}[/green]")
        
        # Update docker-compose.yml
        self.update_docker_compose()
    
    def update_docker_compose(self):
        """Update docker-compose.yml with new instance"""
        compose_file = Path(__file__).parent.parent.parent / "docker-compose.yml"
        
        # This is a simplified example
        # In production, you'd properly parse and update the YAML
        console.print(f"[yellow]Note: Remember to update docker-compose.yml to include this instance[/yellow]")
        console.print(f"\nTo start this instance, run:")
        console.print(f"[bold cyan]docker-compose up -d {self.config['instance_id']}[/bold cyan]")
    
    def run(self):
        """Run the setup wizard"""
        try:
            self.show_welcome()
            
            if not Confirm.ask("\nProceed with setup?", default=True):
                console.print("[yellow]Setup cancelled[/yellow]")
                return
            
            self.configure_instance()
            self.configure_connection()
            self.discover_devices()
            self.configure_groups()
            self.configure_advanced()
            self.show_summary()
            
            if Confirm.ask("\n[bold]Save this configuration?[/bold]", default=True):
                self.save_configuration()
                
                console.print("\n[bold green]✓ Setup complete![/bold green]")
                console.print("\nNext steps:")
                console.print("1. Review the configuration in instances/")
                console.print("2. Update docker-compose.yml if needed")
                console.print("3. Start the connector with docker-compose")
            else:
                console.print("[yellow]Configuration not saved[/yellow]")
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Setup cancelled by user[/yellow]")
            sys.exit(0)
        except Exception as e:
            console.print(f"\n[bold red]Error: {e}[/bold red]")
            import traceback
            traceback.print_exc()
            sys.exit(1)

def main():
    """Main entry point"""
    setup = ConnectorSetup()
    setup.run()

if __name__ == "__main__":
    main()