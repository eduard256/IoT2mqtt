#!/usr/bin/env python3
"""
Template Connector - Management CLI
Manage existing instances (edit, sync, delete)
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
import shutil

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt
from rich import box
from rich.text import Text
from rich.columns import Columns

console = Console()

class ConnectorManager:
    """Manage Template Connector instances"""
    
    def __init__(self):
        self.instances_dir = Path(__file__).parent / "instances"
        self.instances = self.load_instances()
        self.selected_instance = None
    
    def load_instances(self) -> Dict[str, Any]:
        """Load all instance configurations"""
        instances = {}
        
        if not self.instances_dir.exists():
            return instances
        
        for config_file in self.instances_dir.glob("*.json"):
            try:
                with open(config_file) as f:
                    config = json.load(f)
                    instances[config_file.stem] = config
            except Exception as e:
                console.print(f"[red]Error loading {config_file}: {e}[/red]")
        
        return instances
    
    def show_instances_list(self):
        """Show list of all instances"""
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]Template Connector - Instance Manager[/bold cyan]",
            border_style="cyan",
            box=box.DOUBLE
        ))
        
        if not self.instances:
            console.print("\n[yellow]No instances configured yet.[/yellow]")
            console.print("Run setup.py to create your first instance.\n")
            return False
        
        # Create table of instances
        table = Table(title="Configured Instances", box=box.ROUNDED)
        table.add_column("#", style="dim", width=3)
        table.add_column("Instance ID", style="cyan")
        table.add_column("Friendly Name", style="green")
        table.add_column("Type")
        table.add_column("Devices", justify="center")
        table.add_column("Status")
        
        for i, (instance_id, config) in enumerate(self.instances.items(), 1):
            # Check if container is running (simplified)
            status = self.get_instance_status(instance_id)
            
            table.add_row(
                str(i),
                instance_id,
                config.get("friendly_name", ""),
                config.get("instance_type", "unknown"),
                str(len(config.get("devices", []))),
                status
            )
        
        console.print(table)
        return True
    
    def get_instance_status(self, instance_id: str) -> str:
        """Get Docker container status for instance"""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name=iot2mqtt_{instance_id}", "--format", "{{.Status}}"],
                capture_output=True,
                text=True
            )
            if result.stdout.strip():
                return "[green]Running[/green]"
            else:
                return "[yellow]Stopped[/yellow]"
        except:
            return "[dim]Unknown[/dim]"
    
    def select_instance(self) -> Optional[str]:
        """Select an instance to manage"""
        if not self.instances:
            return None
        
        instance_list = list(self.instances.keys())
        
        console.print("\n[bold]Select instance to manage:[/bold]")
        choice = IntPrompt.ask(
            "Instance number (0 to cancel)",
            min_value=0,
            max_value=len(instance_list)
        )
        
        if choice == 0:
            return None
        
        return instance_list[choice - 1]
    
    def show_instance_menu(self):
        """Show management menu for selected instance"""
        config = self.instances[self.selected_instance]
        
        console.clear()
        console.print(Panel.fit(
            f"[bold cyan]Managing: {config['friendly_name']}[/bold cyan]\n"
            f"[dim]Instance ID: {self.selected_instance}[/dim]",
            border_style="cyan"
        ))
        
        # Show instance info
        info_cols = Columns([
            f"[cyan]Type:[/cyan] {config['instance_type']}",
            f"[cyan]Devices:[/cyan] {len(config.get('devices', []))}",
            f"[cyan]Groups:[/cyan] {len(config.get('groups', []))}",
            f"[cyan]Status:[/cyan] {self.get_instance_status(self.selected_instance)}"
        ], padding=(0, 2))
        console.print(info_cols)
        
        # Menu options
        console.print("\n[bold]Available Actions:[/bold]\n")
        console.print("  [1] View configuration")
        console.print("  [2] Edit configuration")
        console.print("  [3] Sync devices (refresh from source)")
        console.print("  [4] Add device")
        console.print("  [5] Remove device")
        console.print("  [6] Manage groups")
        console.print("  [7] View logs")
        console.print("  [8] Restart container")
        console.print("  [9] Delete instance")
        console.print("  [0] Back to instance list")
        
        return Prompt.ask("\nYour choice", choices=list(map(str, range(10))))
    
    def view_configuration(self):
        """View instance configuration"""
        config = self.instances[self.selected_instance]
        
        console.clear()
        console.print(Panel.fit(
            f"[bold cyan]Configuration: {self.selected_instance}[/bold cyan]",
            border_style="cyan"
        ))
        
        # Basic settings
        console.print("\n[bold]Basic Settings:[/bold]")
        table = Table(show_header=False, box=None)
        table.add_column("Property", style="cyan")
        table.add_column("Value")
        
        table.add_row("Instance ID", config["instance_id"])
        table.add_row("Friendly Name", config["friendly_name"])
        table.add_row("Type", config["instance_type"])
        table.add_row("Update Interval", f"{config.get('update_interval', 10)}s")
        
        console.print(table)
        
        # Connection settings (hide sensitive data)
        console.print("\n[bold]Connection:[/bold]")
        conn_table = Table(show_header=False, box=None)
        conn_table.add_column("Property", style="cyan")
        conn_table.add_column("Value")
        
        for key, value in config.get("connection", {}).items():
            if "password" in key.lower() or "token" in key.lower() or "key" in key.lower():
                value = "********"
            conn_table.add_row(key, str(value))
        
        console.print(conn_table)
        
        # Devices
        if config.get("devices"):
            console.print("\n[bold]Devices:[/bold]")
            for device in config["devices"]:
                status = "✓" if device.get("enabled", True) else "✗"
                area = f" [{device['area']}]" if device.get("area") else ""
                console.print(f"  {status} {device['friendly_name']} ({device['device_id']}){area}")
        
        # Groups
        if config.get("groups"):
            console.print("\n[bold]Groups:[/bold]")
            for group in config["groups"]:
                console.print(f"  • {group['name']} - {len(group['devices'])} devices")
        
        input("\n[Press Enter to continue]")
    
    def edit_configuration(self):
        """Edit instance configuration"""
        config = self.instances[self.selected_instance]
        
        console.clear()
        console.print(Panel.fit(
            f"[bold cyan]Edit Configuration: {self.selected_instance}[/bold cyan]",
            border_style="cyan"
        ))
        
        console.print("\n[bold]What would you like to edit?[/bold]\n")
        console.print("  [1] Friendly name")
        console.print("  [2] Connection settings")
        console.print("  [3] Update interval")
        console.print("  [4] MQTT settings")
        console.print("  [5] Error handling")
        console.print("  [0] Cancel")
        
        choice = Prompt.ask("Your choice", choices=["0", "1", "2", "3", "4", "5"])
        
        if choice == "1":
            config["friendly_name"] = Prompt.ask(
                "New friendly name",
                default=config["friendly_name"]
            )
        elif choice == "2":
            self.edit_connection_settings(config)
        elif choice == "3":
            config["update_interval"] = IntPrompt.ask(
                "Update interval (seconds)",
                default=config.get("update_interval", 10)
            )
        elif choice == "4":
            self.edit_mqtt_settings(config)
        elif choice == "5":
            self.edit_error_handling(config)
        else:
            return
        
        # Save changes
        if Confirm.ask("\nSave changes?", default=True):
            self.save_instance_config(self.selected_instance, config)
            console.print("[green]Configuration updated[/green]")
            
            if self.get_instance_status(self.selected_instance) == "[green]Running[/green]":
                if Confirm.ask("Restart container to apply changes?", default=True):
                    self.restart_container()
    
    def edit_connection_settings(self, config: Dict[str, Any]):
        """Edit connection settings"""
        console.print("\n[bold]Connection Settings:[/bold]")
        
        for key in config.get("connection", {}).keys():
            if "password" not in key.lower() and "token" not in key.lower():
                current = config["connection"][key]
                new_value = Prompt.ask(f"  {key}", default=str(current))
                
                # Convert to appropriate type
                if isinstance(current, int):
                    config["connection"][key] = int(new_value)
                elif isinstance(current, bool):
                    config["connection"][key] = new_value.lower() == "true"
                else:
                    config["connection"][key] = new_value
        
        # Password change
        if Confirm.ask("\nChange password/token?", default=False):
            import getpass
            for key in config.get("connection", {}).keys():
                if "password" in key.lower() or "token" in key.lower():
                    config["connection"][key] = getpass.getpass(f"  New {key}: ")
    
    def edit_mqtt_settings(self, config: Dict[str, Any]):
        """Edit MQTT settings"""
        if "mqtt" not in config:
            config["mqtt"] = {}
        
        console.print("\n[bold]MQTT Settings:[/bold]")
        
        config["mqtt"]["qos"] = IntPrompt.ask(
            "  QoS level",
            default=config["mqtt"].get("qos", 1),
            choices=["0", "1", "2"]
        )
        
        config["mqtt"]["retain_state"] = Confirm.ask(
            "  Retain state messages?",
            default=config["mqtt"].get("retain_state", True)
        )
        
        telemetry_modes = ["individual", "batch"]
        current_mode = config["mqtt"].get("telemetry_mode", "individual")
        console.print(f"\n  Telemetry mode (current: {current_mode}):")
        for i, mode in enumerate(telemetry_modes, 1):
            console.print(f"    [{i}] {mode}")
        
        choice = IntPrompt.ask("  Your choice", default=1, choices=["1", "2"])
        config["mqtt"]["telemetry_mode"] = telemetry_modes[choice - 1]
    
    def edit_error_handling(self, config: Dict[str, Any]):
        """Edit error handling settings"""
        if "error_handling" not in config:
            config["error_handling"] = {}
        
        console.print("\n[bold]Error Handling:[/bold]")
        
        config["error_handling"]["max_retries"] = IntPrompt.ask(
            "  Max retries",
            default=config["error_handling"].get("max_retries", 3)
        )
        
        config["error_handling"]["retry_interval"] = IntPrompt.ask(
            "  Retry interval (ms)",
            default=config["error_handling"].get("retry_interval", 5000)
        )
        
        config["error_handling"]["backoff_multiplier"] = IntPrompt.ask(
            "  Backoff multiplier",
            default=config["error_handling"].get("backoff_multiplier", 2)
        )
    
    def sync_devices(self):
        """Sync devices from source"""
        console.print("\n[yellow]Device sync not implemented in template[/yellow]")
        console.print("This feature should be customized for your specific connector")
        input("\n[Press Enter to continue]")
    
    def add_device(self):
        """Add a new device to instance"""
        config = self.instances[self.selected_instance]
        
        console.clear()
        console.print(Panel.fit(
            f"[bold cyan]Add Device to {self.selected_instance}[/bold cyan]",
            border_style="cyan"
        ))
        
        device = {
            "device_id": Prompt.ask("\nDevice ID"),
            "friendly_name": Prompt.ask("Friendly name"),
            "model": Prompt.ask("Model", default="Generic Device"),
            "enabled": True,
            "capabilities": {}
        }
        
        # Set global ID
        device["global_id"] = f"{config['instance_id']}_{device['device_id']}"
        
        # Area
        area = Prompt.ask("Area/Room (optional)", default="")
        if area:
            device["area"] = area
        
        # Basic capabilities
        if Confirm.ask("Can control power?", default=True):
            device["capabilities"]["power"] = {"settable": True}
        
        if Confirm.ask("Has temperature sensor?", default=False):
            device["capabilities"]["temperature"] = {"settable": False}
        
        # Add to config
        if "devices" not in config:
            config["devices"] = []
        
        config["devices"].append(device)
        
        # Save
        self.save_instance_config(self.selected_instance, config)
        console.print(f"\n[green]Added device '{device['friendly_name']}'[/green]")
        
        if self.get_instance_status(self.selected_instance) == "[green]Running[/green]":
            if Confirm.ask("Restart container to apply changes?", default=True):
                self.restart_container()
    
    def remove_device(self):
        """Remove a device from instance"""
        config = self.instances[self.selected_instance]
        
        if not config.get("devices"):
            console.print("[yellow]No devices to remove[/yellow]")
            input("\n[Press Enter to continue]")
            return
        
        console.clear()
        console.print(Panel.fit(
            f"[bold cyan]Remove Device from {self.selected_instance}[/bold cyan]",
            border_style="cyan"
        ))
        
        # List devices
        console.print("\n[bold]Select device to remove:[/bold]")
        for i, device in enumerate(config["devices"], 1):
            console.print(f"  [{i}] {device['friendly_name']} ({device['device_id']})")
        console.print("  [0] Cancel")
        
        choice = IntPrompt.ask(
            "\nYour choice",
            min_value=0,
            max_value=len(config["devices"])
        )
        
        if choice == 0:
            return
        
        removed = config["devices"].pop(choice - 1)
        
        # Also remove from groups
        for group in config.get("groups", []):
            if removed["device_id"] in group["devices"]:
                group["devices"].remove(removed["device_id"])
        
        # Save
        self.save_instance_config(self.selected_instance, config)
        console.print(f"\n[green]Removed device '{removed['friendly_name']}'[/green]")
        
        if self.get_instance_status(self.selected_instance) == "[green]Running[/green]":
            if Confirm.ask("Restart container to apply changes?", default=True):
                self.restart_container()
    
    def view_logs(self):
        """View container logs"""
        console.print("\n[cyan]Fetching logs...[/cyan]\n")
        
        try:
            result = subprocess.run(
                ["docker", "logs", "--tail", "50", f"iot2mqtt_{self.selected_instance}"],
                capture_output=True,
                text=True
            )
            
            if result.stdout:
                console.print(result.stdout)
            if result.stderr:
                console.print(f"[red]{result.stderr}[/red]")
                
        except Exception as e:
            console.print(f"[red]Error fetching logs: {e}[/red]")
        
        input("\n[Press Enter to continue]")
    
    def restart_container(self):
        """Restart Docker container"""
        console.print("\n[yellow]Restarting container...[/yellow]")
        
        try:
            subprocess.run(
                ["docker", "restart", f"iot2mqtt_{self.selected_instance}"],
                check=True
            )
            console.print("[green]Container restarted successfully[/green]")
        except Exception as e:
            console.print(f"[red]Error restarting container: {e}[/red]")
    
    def delete_instance(self):
        """Delete instance configuration"""
        config = self.instances[self.selected_instance]
        
        console.print(f"\n[bold red]Warning![/bold red]")
        console.print(f"This will delete the instance '{config['friendly_name']}'")
        console.print("This action cannot be undone!")
        
        if Confirm.ask("\nAre you sure?", default=False):
            # Stop container if running
            if self.get_instance_status(self.selected_instance) == "[green]Running[/green]":
                console.print("Stopping container...")
                try:
                    subprocess.run(
                        ["docker", "stop", f"iot2mqtt_{self.selected_instance}"],
                        check=True
                    )
                except:
                    pass
            
            # Delete config file
            config_file = self.instances_dir / f"{self.selected_instance}.json"
            config_file.unlink()
            
            # Remove from loaded instances
            del self.instances[self.selected_instance]
            self.selected_instance = None
            
            console.print(f"[green]Instance deleted[/green]")
            input("\n[Press Enter to continue]")
    
    def save_instance_config(self, instance_id: str, config: Dict[str, Any]):
        """Save instance configuration"""
        config_file = self.instances_dir / f"{instance_id}.json"
        
        # Backup existing
        if config_file.exists():
            backup = config_file.with_suffix(".json.bak")
            shutil.copy(config_file, backup)
        
        # Save new config
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Reload
        self.instances[instance_id] = config
    
    def run(self):
        """Main run loop"""
        while True:
            if not self.show_instances_list():
                break
            
            self.selected_instance = self.select_instance()
            if not self.selected_instance:
                break
            
            while self.selected_instance:
                choice = self.show_instance_menu()
                
                if choice == "0":
                    self.selected_instance = None
                elif choice == "1":
                    self.view_configuration()
                elif choice == "2":
                    self.edit_configuration()
                elif choice == "3":
                    self.sync_devices()
                elif choice == "4":
                    self.add_device()
                elif choice == "5":
                    self.remove_device()
                elif choice == "6":
                    console.print("\n[yellow]Group management not yet implemented[/yellow]")
                    input("[Press Enter to continue]")
                elif choice == "7":
                    self.view_logs()
                elif choice == "8":
                    self.restart_container()
                elif choice == "9":
                    self.delete_instance()

def main():
    """Main entry point"""
    try:
        manager = ConnectorManager()
        manager.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()