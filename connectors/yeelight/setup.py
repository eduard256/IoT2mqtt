#!/usr/bin/env python3
"""
Yeelight Connector - Setup wizard
Interactive CLI for creating Yeelight instance configuration
"""

import os
import sys
import json
import getpass
from pathlib import Path
from typing import Dict, Any, List, Optional
import socket
import time

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.columns import Columns
from rich import box
from rich.text import Text

# Import yeelight for discovery
try:
    from yeelight import discover_bulbs, Bulb
except ImportError:
    print("ERROR: yeelight library not installed")
    print("Please run: pip install yeelight")
    sys.exit(1)

console = Console()

class YeelightSetup:
    """Interactive setup wizard for Yeelight Connector"""
    
    def __init__(self):
        self.config = {
            "instance_id": "",
            "instance_type": "device",  # device, account, service
            "connector_type": "yeelight",
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
        
        # Yeelight-specific ASCII art
        logo = """
        ██╗   ██╗███████╗███████╗██╗     ██╗ ██████╗ ██╗  ██╗████████╗
        ╚██╗ ██╔╝██╔════╝██╔════╝██║     ██║██╔════╝ ██║  ██║╚══██╔══╝
         ╚████╔╝ █████╗  █████╗  ██║     ██║██║  ███╗███████║   ██║   
          ╚██╔╝  ██╔══╝  ██╔══╝  ██║     ██║██║   ██║██╔══██║   ██║   
           ██║   ███████╗███████╗███████╗██║╚██████╔╝██║  ██║   ██║   
           ╚═╝   ╚══════╝╚══════╝╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   
        """
        
        console.print(Panel.fit(
            f"[bold cyan]{logo}[/bold cyan]\n\n"
            "[bold]Yeelight Smart Bulb Connector Setup[/bold]\n"
            "[dim]Configure your Yeelight devices for IoT2MQTT[/dim]",
            border_style="cyan",
            box=box.DOUBLE
        ))
        
        console.print("\n[yellow]This wizard will help you discover and configure Yeelight bulbs.[/yellow]")
        console.print("Make sure your bulbs are powered on and connected to the same network.\n")
    
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
        
        # For Yeelight, always use local device type
        self.config["instance_type"] = "device"
    
    def configure_connection(self):
        """Configure Yeelight connection settings"""
        console.print("\n")
        console.print(Panel.fit(
            "[bold cyan]Step 2: Connection Settings[/bold cyan]",
            border_style="cyan"
        ))
        
        console.print("\n[bold]Yeelight Connection Settings[/bold]")
        
        # Discovery settings
        self.config["discovery_enabled"] = Confirm.ask(
            "  Enable automatic device discovery?",
            default=True
        )
        
        if self.config["discovery_enabled"]:
            while True:
                interval = IntPrompt.ask(
                    "  Discovery interval (seconds)",
                    default=300
                )
                if 60 <= interval <= 3600:
                    self.config["discovery_interval"] = interval
                    break
                else:
                    console.print("[red]Please enter a value between 60 and 3600[/red]")
        
        # Effect settings
        console.print("\n[bold]Effect Settings[/bold]")
        console.print("[dim]Default transition settings for all devices[/dim]")
        
        effect_types = ["smooth", "sudden"]
        console.print("  Transition effect:")
        for i, effect in enumerate(effect_types, 1):
            console.print(f"    [{i}] {effect}")
        
        choice = IntPrompt.ask("  Your choice", default=1)
        if choice not in [1, 2]:
            console.print("[red]Please enter 1 or 2[/red]")
            choice = 1
        self.config["effect_type"] = effect_types[choice - 1]
        
        while True:
            duration = IntPrompt.ask(
                "  Transition duration (ms)",
                default=300
            )
            if 30 <= duration <= 10000:
                self.config["duration"] = duration
                break
            else:
                console.print("[red]Please enter a value between 30 and 10000[/red]")
    
    def discover_devices(self):
        """Discover and configure Yeelight devices"""
        console.print("\n")
        console.print(Panel.fit(
            "[bold cyan]Step 3: Device Discovery[/bold cyan]",
            border_style="cyan"
        ))
        
        discovered = []
        
        if Confirm.ask("\nSearch for Yeelight devices on network?", default=True):
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("[yellow]Searching for Yeelight devices...[/yellow]", total=None)
                
                try:
                    # Actual Yeelight discovery
                    bulbs = discover_bulbs(timeout=10)
                    
                    for bulb_info in bulbs:
                        ip = bulb_info['ip']
                        capabilities = bulb_info.get('capabilities', {})
                        
                        device = {
                            "id": capabilities.get('id', ip.replace('.', '_')),
                            "name": capabilities.get('name', ''),
                            "model": capabilities.get('model', 'unknown'),
                            "ip": ip,
                            "port": bulb_info.get('port', 55443),
                            "fw_ver": capabilities.get('fw_ver', ''),
                            "support": capabilities.get('support', []),
                            "capabilities": self._parse_yeelight_capabilities(capabilities)
                        }
                        discovered.append(device)
                    
                except Exception as e:
                    console.print(f"[red]Discovery error: {e}[/red]")
                
                progress.update(task, completed=True)
        
        if not discovered:
            console.print("[yellow]No devices discovered.[/yellow]")
            
            if Confirm.ask("Would you like to add devices manually?", default=True):
                discovered = self.manual_device_config()
                selected_devices = discovered  # Set selected_devices for manual config
            else:
                selected_devices = []  # No devices if user doesn't want to add manually
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
        """Manual Yeelight device configuration"""
        devices = []
        
        while True:
            console.print("\n[bold]Add Yeelight Device Manually[/bold]")
            
            ip = Prompt.ask("  Device IP address")
            
            # Test connection
            console.print(f"Testing connection to {ip}...")
            test_success = False
            try:
                bulb = Bulb(ip)
                props = bulb.get_properties()
                if props:
                    test_success = True
                    console.print("[green]✓ Connection successful![/green]")
            except:
                console.print("[red]✗ Could not connect to device[/red]")
            
            if not test_success and not Confirm.ask("  Add anyway?", default=False):
                continue
            
            device = {
                "id": Prompt.ask("  Device ID", default=ip.replace('.', '_')),
                "name": Prompt.ask("  Device name"),
                "model": Prompt.ask("  Device model", default="color"),
                "ip": ip,
                "port": IntPrompt.ask("  Device port", default=55443),
                "capabilities": {
                    "power": {"settable": True},
                    "brightness": {"settable": True, "min": 1, "max": 100},
                    "color_temp": {"settable": True, "min": 1700, "max": 6500}
                }
            }
            
            # Ask about additional capabilities
            if Confirm.ask("  Supports RGB color?", default=True):
                device["capabilities"]["rgb"] = {"settable": True}
            
            if Confirm.ask("  Has background light (ceiling)?", default=False):
                device["capabilities"]["background"] = {"settable": True}
            
            devices.append(device)
            
            if not Confirm.ask("\nAdd another device?", default=False):
                break
        
        return devices
    
    def _parse_yeelight_capabilities(self, caps: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Yeelight capabilities"""
        capabilities = {
            "power": {"settable": True}
        }
        
        support = caps.get('support', [])
        
        if 'set_bright' in support:
            capabilities["brightness"] = {"settable": True, "min": 1, "max": 100}
        
        if 'set_ct_abx' in support:
            capabilities["color_temp"] = {"settable": True, "min": 1700, "max": 6500}
        
        if 'set_rgb' in support:
            capabilities["rgb"] = {"settable": True}
        
        if 'set_hsv' in support:
            capabilities["hsv"] = {"settable": True}
        
        if 'bg_set_power' in support:
            capabilities["background"] = {"settable": True}
        
        return capabilities
    
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
        
        choice = IntPrompt.ask("  Your choice", default=1)
        if choice not in [1, 2]:
            console.print("[red]Please enter 1 or 2[/red]")
            choice = 1
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
        import yaml
        import subprocess
        
        compose_file = Path(__file__).parent.parent.parent / "docker-compose.yml"
        
        # Read existing or create new docker-compose.yml
        if compose_file.exists():
            with open(compose_file) as f:
                compose_data = yaml.safe_load(f) or {}
        else:
            compose_data = {"version": "3.8", "services": {}, "networks": {}}
        
        # Ensure networks section exists
        if "networks" not in compose_data:
            compose_data["networks"] = {}
        if "iot2mqtt" not in compose_data["networks"]:
            compose_data["networks"]["iot2mqtt"] = {"driver": "bridge"}
        
        # Add service for this instance
        service_name = f"yeelight_{self.config['instance_id']}"
        compose_data["services"][service_name] = {
            "build": "./connectors/yeelight",
            "container_name": f"iot2mqtt_{service_name}",
            "restart": "unless-stopped",
            "volumes": [
                "./shared:/app/shared:ro",
                f"./connectors/yeelight/instances:/app/instances:ro"
            ],
            "environment": [
                f"INSTANCE_NAME={self.config['instance_id']}",
                "MODE=production",
                "PYTHONUNBUFFERED=1"
            ],
            "env_file": [
                ".env"
            ],
            "networks": [
                "iot2mqtt"
            ],
            "depends_on": []
        }
        
        # Save docker-compose.yml
        with open(compose_file, 'w') as f:
            yaml.dump(compose_data, f, default_flow_style=False, sort_keys=False)
        
        console.print(f"[green]✓ Updated docker-compose.yml[/green]")
        
        # Create Dockerfile if not exists
        self.create_dockerfile()
        
        # Build and start container
        if Confirm.ask("\n[bold]Start the container now?[/bold]", default=True):
            console.print("\n[yellow]Building Docker image...[/yellow]")
            result = subprocess.run(
                ["docker-compose", "build", service_name],
                cwd=compose_file.parent,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                console.print("[green]✓ Docker image built successfully[/green]")
                
                console.print("\n[yellow]Starting container...[/yellow]")
                result = subprocess.run(
                    ["docker-compose", "up", "-d", service_name],
                    cwd=compose_file.parent,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    console.print(f"[green]✓ Container {service_name} started successfully[/green]")
                    
                    # Wait a moment for container to start
                    time.sleep(3)
                    
                    # Show container logs
                    console.print("\n[bold]Container Logs:[/bold]")
                    console.print("[dim]" + "="*60 + "[/dim]")
                    
                    log_result = subprocess.run(
                        ["docker-compose", "logs", "--tail=100", service_name],
                        cwd=compose_file.parent,
                        capture_output=True,
                        text=True
                    )
                    
                    # Display all logs
                    if log_result.stdout:
                        # Color code the logs
                        for line in log_result.stdout.split('\n'):
                            if line:
                                if 'error' in line.lower() or 'exception' in line.lower():
                                    console.print(f"[red]{line}[/red]")
                                elif 'warning' in line.lower() or 'warn' in line.lower():
                                    console.print(f"[yellow]{line}[/yellow]")
                                elif 'connected' in line.lower() or 'success' in line.lower() or '✓' in line:
                                    console.print(f"[green]{line}[/green]")
                                elif 'mqtt' in line.lower():
                                    console.print(f"[cyan]{line}[/cyan]")
                                else:
                                    console.print(f"[dim]{line}[/dim]")
                    
                    console.print("[dim]" + "="*60 + "[/dim]")
                    
                    # Check for errors
                    if "error" in log_result.stdout.lower() or "exception" in log_result.stdout.lower():
                        console.print("\n[yellow]⚠ Warnings or errors detected in logs above[/yellow]")
                        console.print("[dim]Check the logs carefully for any issues[/dim]")
                    else:
                        console.print("\n[green]✓ Container is running successfully![/green]")
                    
                    console.print(f"\n[dim]Monitor real-time logs with: docker-compose logs -f {service_name}[/dim]")
                else:
                    console.print(f"[red]Failed to start container: {result.stderr}[/red]")
            else:
                console.print(f"[red]Failed to build image: {result.stderr}[/red]")
    
    def create_dockerfile(self):
        """Create Dockerfile if not exists"""
        dockerfile = Path(__file__).parent / "Dockerfile"
        
        if not dockerfile.exists():
            dockerfile_content = """FROM python:3.11-slim

WORKDIR /app

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./

# Environment variables
ENV MODE=production
ENV PYTHONUNBUFFERED=1

# Run the connector
CMD ["python", "-u", "main.py"]
"""
            with open(dockerfile, 'w') as f:
                f.write(dockerfile_content)
            
            console.print("[green]✓ Created Dockerfile[/green]")
    
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
    setup = YeelightSetup()
    setup.run()

if __name__ == "__main__":
    main()