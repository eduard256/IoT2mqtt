#!/usr/bin/env python3
"""
IoT2MQTT - Main launcher with beautiful TUI
Direct IoT to MQTT bridge for minimal latency
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
import json

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
from rich.text import Text
from rich import box
from rich.prompt import Prompt, Confirm
import time

console = Console()

@dataclass
class ConnectorInfo:
    """Information about a connector"""
    name: str
    path: Path
    instances: List[str]
    has_setup: bool
    has_manage: bool

class IoT2MQTTLauncher:
    """Main launcher for IoT2MQTT system"""
    
    def __init__(self):
        self.base_path = Path(__file__).parent
        self.connectors_path = self.base_path / "connectors"
        self.selected_index = 0
        self.connectors: List[ConnectorInfo] = []
        self.base_topic = self.load_base_topic()
        
    def load_base_topic(self) -> str:
        """Load base topic from .env file"""
        env_file = self.base_path / ".env"
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if line.startswith("MQTT_BASE_TOPIC="):
                        return line.split("=", 1)[1].strip()
        return "IoT2mqtt"
    
    def check_initial_setup(self) -> bool:
        """Check if initial MQTT setup is done"""
        env_file = self.base_path / ".env"
        if not env_file.exists():
            return False
        
        # Check if essential variables exist
        required_vars = ["MQTT_HOST", "MQTT_PORT", "MQTT_BASE_TOPIC"]
        with open(env_file) as f:
            content = f.read()
            return all(f"{var}=" in content for var in required_vars)
    
    def run_initial_setup(self):
        """Run initial MQTT setup"""
        console.clear()
        console.print(Panel.fit(
            "[bold yellow]First Run Detected![/bold yellow]\n"
            "[dim]Let's configure MQTT connection first[/dim]",
            border_style="yellow"
        ))
        time.sleep(2)
        
        setup_script = self.base_path / "setup_mqtt.py"
        if setup_script.exists():
            subprocess.run([sys.executable, str(setup_script)])
        else:
            console.print("[red]Error: setup_mqtt.py not found![/red]")
            sys.exit(1)
    
    def scan_connectors(self):
        """Scan connectors directory for available connectors"""
        self.connectors = []
        
        if not self.connectors_path.exists():
            return
        
        for connector_dir in sorted(self.connectors_path.iterdir()):
            if not connector_dir.is_dir() or connector_dir.name.startswith('_'):
                continue
            
            # Count instances
            instances_dir = connector_dir / "instances"
            instances = []
            if instances_dir.exists():
                instances = [f.stem for f in instances_dir.glob("*.json")]
            
            # Check for setup and manage scripts
            has_setup = (connector_dir / "setup.py").exists()
            has_manage = (connector_dir / "manage.py").exists()
            
            self.connectors.append(ConnectorInfo(
                name=connector_dir.name,
                path=connector_dir,
                instances=instances,
                has_setup=has_setup,
                has_manage=has_manage
            ))
    
    def create_header(self) -> Panel:
        """Create beautiful header with ASCII art"""
        ascii_art = """
╦╔═╗╔╦╗  ╔═╗  ╔╦╗╔═╗╔╦╗╔╦╗
║║ ║ ║   ╔═╝  ║║║║═╬╦╝║ ║ 
╩╚═╝ ╩   ╚═╝  ╩ ╩╚═╩╚ ╩ ╩
        """
        
        header_text = Text.from_markup(
            f"{ascii_art}\n"
            f"[bold cyan]Direct IoT to MQTT Bridge[/bold cyan]\n"
            f"[dim]Base Topic: {self.base_topic}[/dim]"
        )
        
        return Panel(
            Align.center(header_text),
            border_style="cyan",
            box=box.DOUBLE
        )
    
    def create_menu(self) -> Table:
        """Create connectors menu table"""
        table = Table(
            show_header=False,
            box=None,
            padding=(0, 2),
            expand=True
        )
        
        table.add_column("", justify="right", width=3)
        table.add_column("Connector", justify="left")
        table.add_column("Instances", justify="center", width=10)
        
        for i, connector in enumerate(self.connectors):
            # Selection indicator
            indicator = ">" if i == self.selected_index else " "
            
            # Connector name with color
            if i == self.selected_index:
                name = f"[bold cyan]{connector.name}[/bold cyan]"
            else:
                name = connector.name
            
            # Instance count
            count = len(connector.instances)
            if count > 0:
                instances = f"[green][{count}][/green]"
            else:
                instances = "[dim][0][/dim]"
            
            table.add_row(indicator, name, instances)
        
        # Add custom connector option
        indicator = ">" if self.selected_index == len(self.connectors) else " "
        name = "[bold yellow]+ Add Custom Connector[/bold yellow]" if self.selected_index == len(self.connectors) else "[dim]+ Add Custom Connector[/dim]"
        table.add_row(indicator, name, "")
        
        return Panel(
            table,
            title="[bold]Available Connectors[/bold]",
            border_style="blue"
        )
    
    def create_footer(self) -> Panel:
        """Create footer with hotkeys"""
        footer_text = (
            "[bold cyan][↑↓][/bold cyan] Navigate  "
            "[bold cyan][Enter][/bold cyan] Select  "
            "[bold cyan][S][/bold cyan] Settings  "
            "[bold cyan][L][/bold cyan] Logs  "
            "[bold cyan][D][/bold cyan] Devices  "
            "[bold cyan][Q][/bold cyan] Quit"
        )
        
        return Panel(
            Align.center(Text.from_markup(footer_text)),
            border_style="dim"
        )
    
    def display_main_menu(self):
        """Display main menu with live updates"""
        layout = Layout()
        layout.split_column(
            Layout(self.create_header(), size=9),
            Layout(self.create_menu(), size=15),
            Layout(self.create_footer(), size=3)
        )
        
        console.clear()
        console.print(layout)
    
    def handle_connector_selection(self, connector: ConnectorInfo):
        """Handle connector selection"""
        if len(connector.instances) == 0:
            # No instances, go directly to setup
            if connector.has_setup:
                self.run_connector_setup(connector)
            else:
                console.print(f"[red]No setup.py found for {connector.name}[/red]")
                input("Press Enter to continue...")
        else:
            # Has instances, show submenu
            self.show_connector_submenu(connector)
    
    def show_connector_submenu(self, connector: ConnectorInfo):
        """Show submenu for connector with instances"""
        console.clear()
        
        console.print(Panel.fit(
            f"[bold cyan]{connector.name.upper()}[/bold cyan]\n"
            f"[dim]Instances: {', '.join(connector.instances)}[/dim]",
            border_style="cyan"
        ))
        
        console.print("\n[bold]What would you like to do?[/bold]\n")
        console.print("  [1] Create new instance")
        console.print("  [2] Manage existing instances")
        console.print("  [0] Back to main menu")
        
        choice = Prompt.ask("\nYour choice", choices=["0", "1", "2"])
        
        if choice == "1":
            self.run_connector_setup(connector)
        elif choice == "2":
            self.run_connector_manage(connector)
    
    def run_connector_setup(self, connector: ConnectorInfo):
        """Run connector setup script"""
        setup_script = connector.path / "setup.py"
        if setup_script.exists():
            console.clear()
            subprocess.run([sys.executable, str(setup_script)])
            input("\nPress Enter to return to main menu...")
        else:
            console.print(f"[red]setup.py not found for {connector.name}[/red]")
            input("Press Enter to continue...")
    
    def run_connector_manage(self, connector: ConnectorInfo):
        """Run connector manage script"""
        manage_script = connector.path / "manage.py"
        if manage_script.exists():
            console.clear()
            subprocess.run([sys.executable, str(manage_script)])
            input("\nPress Enter to return to main menu...")
        else:
            console.print(f"[red]manage.py not found for {connector.name}[/red]")
            input("Press Enter to continue...")
    
    def handle_add_custom_connector(self):
        """Handle adding custom connector"""
        console.clear()
        console.print(Panel.fit(
            "[bold yellow]Add Custom Connector[/bold yellow]\n"
            "[dim]Create a new connector from template[/dim]",
            border_style="yellow"
        ))
        
        name = Prompt.ask("\nConnector name (lowercase, no spaces)")
        if not name or not name.replace("_", "").replace("-", "").isalnum():
            console.print("[red]Invalid connector name![/red]")
            input("Press Enter to continue...")
            return
        
        # Check if already exists
        connector_path = self.connectors_path / name
        if connector_path.exists():
            console.print(f"[red]Connector {name} already exists![/red]")
            input("Press Enter to continue...")
            return
        
        # Copy template
        template_path = self.connectors_path / "_template"
        if not template_path.exists():
            console.print("[red]Template connector not found![/red]")
            input("Press Enter to continue...")
            return
        
        console.print(f"\n[yellow]Creating connector {name}...[/yellow]")
        
        # Copy template directory
        import shutil
        shutil.copytree(template_path, connector_path)
        
        console.print(f"[green]✓ Connector {name} created successfully![/green]")
        console.print(f"\nNext steps:")
        console.print(f"1. Edit {connector_path}/connector.py to implement your device logic")
        console.print(f"2. Edit {connector_path}/setup.py for configuration UI")
        console.print(f"3. Update {connector_path}/requirements.txt with dependencies")
        
        input("\nPress Enter to continue...")
    
    def show_settings(self):
        """Show settings menu"""
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]Settings[/bold cyan]",
            border_style="cyan"
        ))
        
        console.print("\n[bold]Options:[/bold]\n")
        console.print("  [1] Reconfigure MQTT connection")
        console.print("  [2] View current configuration")
        console.print("  [3] Export configuration")
        console.print("  [0] Back to main menu")
        
        choice = Prompt.ask("\nYour choice", choices=["0", "1", "2", "3"])
        
        if choice == "1":
            self.run_initial_setup()
        elif choice == "2":
            self.view_configuration()
        elif choice == "3":
            self.export_configuration()
    
    def view_configuration(self):
        """View current configuration"""
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]Current Configuration[/bold cyan]",
            border_style="cyan"
        ))
        
        env_file = self.base_path / ".env"
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if "PASSWORD" in line or "SECRET" in line:
                        key = line.split("=")[0]
                        console.print(f"{key}=********")
                    else:
                        console.print(line.strip())
        
        input("\nPress Enter to continue...")
    
    def export_configuration(self):
        """Export configuration for backup"""
        # TODO: Implement configuration export
        console.print("[yellow]Configuration export not yet implemented[/yellow]")
        input("Press Enter to continue...")
    
    def show_logs(self):
        """Show system logs"""
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]System Logs[/bold cyan]",
            border_style="cyan"
        ))
        
        # TODO: Implement log viewer
        console.print("[yellow]Log viewer not yet implemented[/yellow]")
        console.print("[dim]Logs will be available through docker-compose logs[/dim]")
        input("\nPress Enter to continue...")
    
    def show_devices(self):
        """Show all devices across instances"""
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]All Devices[/bold cyan]",
            border_style="cyan"
        ))
        
        table = Table(title="Registered Devices")
        table.add_column("Instance", style="cyan")
        table.add_column("Device ID", style="green")
        table.add_column("Model")
        table.add_column("Status")
        
        device_count = 0
        for connector in self.connectors:
            instances_dir = connector.path / "instances"
            if instances_dir.exists():
                for instance_file in instances_dir.glob("*.json"):
                    try:
                        with open(instance_file) as f:
                            config = json.load(f)
                            for device in config.get("devices", []):
                                table.add_row(
                                    config.get("instance_id", instance_file.stem),
                                    device.get("device_id", "unknown"),
                                    device.get("model", "unknown"),
                                    "[green]enabled[/green]" if device.get("enabled", True) else "[red]disabled[/red]"
                                )
                                device_count += 1
                    except Exception as e:
                        console.print(f"[red]Error reading {instance_file}: {e}[/red]")
        
        if device_count > 0:
            console.print(table)
        else:
            console.print("[yellow]No devices configured yet[/yellow]")
        
        input("\nPress Enter to continue...")
    
    def run(self):
        """Main run loop"""
        # Check initial setup
        if not self.check_initial_setup():
            self.run_initial_setup()
            # Reload base topic after setup
            self.base_topic = self.load_base_topic()
        
        # Main loop
        while True:
            self.scan_connectors()
            self.display_main_menu()
            
            # Get user input
            key = console.input()
            
            if key.lower() == 'q':
                if Confirm.ask("\n[yellow]Are you sure you want to quit?[/yellow]"):
                    console.clear()
                    console.print("[bold green]Thank you for using IoT2MQTT![/bold green]")
                    break
            elif key.lower() == 's':
                self.show_settings()
            elif key.lower() == 'l':
                self.show_logs()
            elif key.lower() == 'd':
                self.show_devices()
            elif key == '\x1b[A' or key == 'k':  # Up arrow or k
                self.selected_index = max(0, self.selected_index - 1)
            elif key == '\x1b[B' or key == 'j':  # Down arrow or j
                max_index = len(self.connectors)
                self.selected_index = min(max_index, self.selected_index + 1)
            elif key == '\r' or key == '\n':  # Enter
                if self.selected_index < len(self.connectors):
                    self.handle_connector_selection(self.connectors[self.selected_index])
                else:
                    self.handle_add_custom_connector()

def main():
    """Main entry point"""
    try:
        launcher = IoT2MQTTLauncher()
        launcher.run()
    except KeyboardInterrupt:
        console.clear()
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")
        sys.exit(1)

if __name__ == "__main__":
    main()