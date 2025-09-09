#!/usr/bin/env python3
"""
IoT2MQTT - MQTT Configuration Setup
Interactive wizard for configuring MQTT connection
"""

import os
import sys
from pathlib import Path
import socket
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich.text import Text
from rich import box
from rich.align import Align

console = Console()

class MQTTSetup:
    """MQTT configuration wizard"""
    
    def __init__(self):
        self.base_path = Path(__file__).parent
        self.env_file = self.base_path / ".env"
        self.config = {}
    
    def show_welcome(self):
        """Show welcome screen"""
        console.clear()
        
        ascii_art = """
╔╦╗╔═╗╔╦╗╔╦╗  ╔═╗╔═╗╔╦╗╦ ╦╔═╗
║║║║═╬╦╝║ ║   ╚═╗║╣  ║ ║ ║╠═╝
╩ ╩╚═╩╚ ╩ ╩   ╚═╝╚═╝ ╩ ╚═╝╩  
        """
        
        welcome_text = Text.from_markup(
            f"{ascii_art}\n\n"
            "[bold cyan]Welcome to IoT2MQTT Setup Wizard[/bold cyan]\n\n"
            "[dim]This wizard will help you configure MQTT connection\n"
            "and other essential settings for your IoT2MQTT bridge[/dim]"
        )
        
        console.print(Panel(
            Align.center(welcome_text),
            border_style="cyan",
            box=box.DOUBLE
        ))
        
        if not Confirm.ask("\n[bold]Ready to begin setup?[/bold]", default=True):
            console.print("[yellow]Setup cancelled[/yellow]")
            sys.exit(0)
    
    def test_mqtt_connection(self, host: str, port: int) -> bool:
        """Test if MQTT broker is reachable"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def configure_mqtt_broker(self):
        """Configure MQTT broker connection"""
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]Step 1: MQTT Broker Configuration[/bold cyan]",
            border_style="cyan"
        ))
        
        # MQTT Host
        console.print("\n[bold]MQTT Broker Host[/bold]")
        console.print("[dim]Enter the hostname or IP address of your MQTT broker[/dim]")
        
        default_host = "localhost"
        # Try to detect common MQTT hosts
        for host in ["localhost", "homeassistant.local", "192.168.1.1"]:
            if self.test_mqtt_connection(host, 1883):
                default_host = host
                console.print(f"[green]✓ Detected MQTT broker at {host}[/green]")
                break
        
        self.config["MQTT_HOST"] = Prompt.ask(
            "  MQTT Host",
            default=default_host
        )
        
        # MQTT Port
        console.print("\n[bold]MQTT Broker Port[/bold]")
        console.print("[dim]Standard port is 1883, SSL/TLS usually 8883[/dim]")
        
        self.config["MQTT_PORT"] = IntPrompt.ask(
            "  MQTT Port",
            default=1883
        )
        
        # Test connection
        console.print("\n[yellow]Testing connection...[/yellow]")
        if self.test_mqtt_connection(self.config["MQTT_HOST"], self.config["MQTT_PORT"]):
            console.print("[green]✓ Connection successful![/green]")
        else:
            console.print("[red]✗ Could not connect to MQTT broker[/red]")
            if not Confirm.ask("Continue anyway?", default=False):
                console.print("[yellow]Setup cancelled[/yellow]")
                sys.exit(0)
        
        # Authentication
        console.print("\n[bold]MQTT Authentication[/bold]")
        if Confirm.ask("  Does your MQTT broker require authentication?", default=False):
            self.config["MQTT_USERNAME"] = Prompt.ask("    Username")
            # For password, we should use a more secure method in production
            import getpass
            self.config["MQTT_PASSWORD"] = getpass.getpass("    Password: ")
        else:
            self.config["MQTT_USERNAME"] = ""
            self.config["MQTT_PASSWORD"] = ""
    
    def configure_base_topic(self):
        """Configure base topic and client settings"""
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]Step 2: MQTT Topics Configuration[/bold cyan]",
            border_style="cyan"
        ))
        
        # Base Topic
        console.print("\n[bold]Base Topic Name[/bold]")
        console.print("[dim]This will be the root topic for all IoT2MQTT messages[/dim]")
        console.print("[dim]Example: 'IoT2mqtt' will create topics like 'IoT2mqtt/instances/...'[/dim]")
        
        self.config["MQTT_BASE_TOPIC"] = Prompt.ask(
            "  Base topic",
            default="IoT2mqtt"
        )
        
        # Client ID Prefix
        console.print("\n[bold]Client ID Prefix[/bold]")
        console.print("[dim]Prefix for MQTT client IDs to avoid conflicts[/dim]")
        
        self.config["MQTT_CLIENT_PREFIX"] = Prompt.ask(
            "  Client ID prefix",
            default="iot2mqtt"
        )
        
        # QoS Level
        console.print("\n[bold]Quality of Service (QoS) Level[/bold]")
        console.print("[dim]0 = At most once, 1 = At least once, 2 = Exactly once[/dim]")
        
        self.config["MQTT_QOS"] = IntPrompt.ask(
            "  QoS level",
            default=1,
            choices=["0", "1", "2"]
        )
        
        # Retain messages
        console.print("\n[bold]Message Retention[/bold]")
        console.print("[dim]Retain last message on broker for new subscribers[/dim]")
        
        self.config["MQTT_RETAIN"] = str(Confirm.ask(
            "  Retain state messages?",
            default=True
        )).lower()
    
    def configure_home_assistant(self):
        """Configure Home Assistant discovery"""
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]Step 3: Home Assistant Integration (Optional)[/bold cyan]",
            border_style="cyan"
        ))
        
        console.print("\n[bold]Home Assistant Discovery[/bold]")
        console.print("[dim]Enable automatic discovery of devices in Home Assistant[/dim]")
        console.print("[dim]This is optional - IoT2MQTT works independently of HA[/dim]")
        
        ha_enabled = Confirm.ask(
            "  Enable Home Assistant discovery?",
            default=False
        )
        
        self.config["HA_DISCOVERY_ENABLED"] = str(ha_enabled).lower()
        
        if ha_enabled:
            console.print("\n[bold]Discovery Prefix[/bold]")
            console.print("[dim]Topic prefix for Home Assistant discovery messages[/dim]")
            
            self.config["HA_DISCOVERY_PREFIX"] = Prompt.ask(
                "  Discovery prefix",
                default="homeassistant"
            )
        else:
            self.config["HA_DISCOVERY_PREFIX"] = "homeassistant"
    
    def configure_advanced(self):
        """Configure advanced settings"""
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]Step 4: Advanced Settings (Optional)[/bold cyan]",
            border_style="cyan"
        ))
        
        if not Confirm.ask("\n[bold]Configure advanced settings?[/bold]", default=False):
            # Set defaults
            self.config["MQTT_KEEPALIVE"] = "60"
            self.config["MQTT_CLEAN_SESSION"] = "true"
            self.config["RESPONSE_TIMEOUT"] = "5"
            self.config["MAX_RETRIES"] = "3"
            return
        
        # Keepalive
        console.print("\n[bold]MQTT Keepalive[/bold]")
        console.print("[dim]Seconds between keepalive pings to broker[/dim]")
        
        self.config["MQTT_KEEPALIVE"] = str(IntPrompt.ask(
            "  Keepalive (seconds)",
            default=60
        ))
        
        # Clean Session
        console.print("\n[bold]Clean Session[/bold]")
        console.print("[dim]Start with clean session on connect[/dim]")
        
        self.config["MQTT_CLEAN_SESSION"] = str(Confirm.ask(
            "  Use clean session?",
            default=True
        )).lower()
        
        # Response Timeout
        console.print("\n[bold]Response Timeout[/bold]")
        console.print("[dim]Seconds to wait for device responses[/dim]")
        
        self.config["RESPONSE_TIMEOUT"] = str(IntPrompt.ask(
            "  Response timeout (seconds)",
            default=5
        ))
        
        # Max Retries
        console.print("\n[bold]Maximum Retries[/bold]")
        console.print("[dim]Number of retry attempts for failed commands[/dim]")
        
        self.config["MAX_RETRIES"] = str(IntPrompt.ask(
            "  Max retries",
            default=3
        ))
    
    def show_summary(self):
        """Show configuration summary"""
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]Configuration Summary[/bold cyan]",
            border_style="cyan"
        ))
        
        table = Table(show_header=False, box=None)
        table.add_column("Setting", style="cyan", width=25)
        table.add_column("Value", style="green")
        
        # Group settings
        table.add_row("[bold]MQTT Broker[/bold]", "")
        table.add_row("  Host", self.config["MQTT_HOST"])
        table.add_row("  Port", str(self.config["MQTT_PORT"]))
        table.add_row("  Username", self.config["MQTT_USERNAME"] or "[dim]Not set[/dim]")
        table.add_row("  Password", "********" if self.config["MQTT_PASSWORD"] else "[dim]Not set[/dim]")
        
        table.add_row("", "")
        table.add_row("[bold]MQTT Settings[/bold]", "")
        table.add_row("  Base Topic", self.config["MQTT_BASE_TOPIC"])
        table.add_row("  Client Prefix", self.config["MQTT_CLIENT_PREFIX"])
        table.add_row("  QoS Level", str(self.config["MQTT_QOS"]))
        table.add_row("  Retain Messages", self.config["MQTT_RETAIN"])
        
        table.add_row("", "")
        table.add_row("[bold]Home Assistant[/bold]", "")
        table.add_row("  Discovery Enabled", self.config["HA_DISCOVERY_ENABLED"])
        if self.config["HA_DISCOVERY_ENABLED"] == "true":
            table.add_row("  Discovery Prefix", self.config["HA_DISCOVERY_PREFIX"])
        
        table.add_row("", "")
        table.add_row("[bold]Advanced[/bold]", "")
        table.add_row("  Keepalive", f"{self.config['MQTT_KEEPALIVE']}s")
        table.add_row("  Clean Session", self.config["MQTT_CLEAN_SESSION"])
        table.add_row("  Response Timeout", f"{self.config['RESPONSE_TIMEOUT']}s")
        table.add_row("  Max Retries", self.config["MAX_RETRIES"])
        
        console.print(table)
    
    def save_configuration(self):
        """Save configuration to .env file"""
        # Check if .env exists and backup
        if self.env_file.exists():
            backup_file = self.env_file.with_suffix('.env.backup')
            console.print(f"\n[yellow]Backing up existing .env to {backup_file.name}[/yellow]")
            self.env_file.rename(backup_file)
        
        # Write new configuration
        with open(self.env_file, 'w') as f:
            f.write("# IoT2MQTT Configuration\n")
            f.write("# Generated by setup_mqtt.py\n\n")
            
            f.write("# MQTT Broker Settings\n")
            f.write(f"MQTT_HOST={self.config['MQTT_HOST']}\n")
            f.write(f"MQTT_PORT={self.config['MQTT_PORT']}\n")
            f.write(f"MQTT_USERNAME={self.config['MQTT_USERNAME']}\n")
            f.write(f"MQTT_PASSWORD={self.config['MQTT_PASSWORD']}\n")
            f.write("\n")
            
            f.write("# MQTT Topics and Client\n")
            f.write(f"MQTT_BASE_TOPIC={self.config['MQTT_BASE_TOPIC']}\n")
            f.write(f"MQTT_CLIENT_PREFIX={self.config['MQTT_CLIENT_PREFIX']}\n")
            f.write(f"MQTT_QOS={self.config['MQTT_QOS']}\n")
            f.write(f"MQTT_RETAIN={self.config['MQTT_RETAIN']}\n")
            f.write("\n")
            
            f.write("# Home Assistant Discovery\n")
            f.write(f"HA_DISCOVERY_ENABLED={self.config['HA_DISCOVERY_ENABLED']}\n")
            f.write(f"HA_DISCOVERY_PREFIX={self.config['HA_DISCOVERY_PREFIX']}\n")
            f.write("\n")
            
            f.write("# Advanced Settings\n")
            f.write(f"MQTT_KEEPALIVE={self.config['MQTT_KEEPALIVE']}\n")
            f.write(f"MQTT_CLEAN_SESSION={self.config['MQTT_CLEAN_SESSION']}\n")
            f.write(f"RESPONSE_TIMEOUT={self.config['RESPONSE_TIMEOUT']}\n")
            f.write(f"MAX_RETRIES={self.config['MAX_RETRIES']}\n")
        
        console.print(f"[green]✓ Configuration saved to {self.env_file}[/green]")
    
    def create_secrets_structure(self):
        """Create secrets directory structure"""
        secrets_dir = self.base_path / "secrets"
        secrets_instances_dir = secrets_dir / "instances"
        
        # Create directories
        secrets_dir.mkdir(exist_ok=True)
        secrets_instances_dir.mkdir(exist_ok=True)
        
        # Create .gitkeep files to preserve structure
        (secrets_dir / ".gitkeep").touch()
        (secrets_instances_dir / ".gitkeep").touch()
        
        # Create example admin secret file
        admin_secret_file = secrets_dir / "mqtt_admin.secret.example"
        with open(admin_secret_file, 'w') as f:
            f.write("# Example MQTT admin credentials\n")
            f.write("# Copy to mqtt_admin.secret and fill in actual values\n")
            f.write("username=admin\n")
            f.write("password=your_admin_password\n")
        
        console.print(f"[green]✓ Created secrets directory structure[/green]")
    
    def show_next_steps(self):
        """Show next steps after setup"""
        console.print("\n")
        console.print(Panel(
            Text.from_markup(
                "[bold green]✓ Setup Complete![/bold green]\n\n"
                "[bold]Next Steps:[/bold]\n"
                "1. Run [cyan]python iot2mqtt.py[/cyan] to start the main launcher\n"
                "2. Add your first connector from the main menu\n"
                "3. Configure your devices\n"
                "4. Start enjoying minimal latency IoT control!\n\n"
                "[dim]For more information, see README.md[/dim]"
            ),
            border_style="green",
            box=box.ROUNDED
        ))
    
    def run(self):
        """Run the setup wizard"""
        try:
            self.show_welcome()
            self.configure_mqtt_broker()
            self.configure_base_topic()
            self.configure_home_assistant()
            self.configure_advanced()
            self.show_summary()
            
            if Confirm.ask("\n[bold]Save this configuration?[/bold]", default=True):
                self.save_configuration()
                self.create_secrets_structure()
                self.show_next_steps()
            else:
                console.print("[yellow]Configuration not saved[/yellow]")
                sys.exit(0)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Setup cancelled by user[/yellow]")
            sys.exit(0)
        except Exception as e:
            console.print(f"\n[bold red]Error during setup: {e}[/bold red]")
            sys.exit(1)

def main():
    """Main entry point"""
    setup = MQTTSetup()
    setup.run()

if __name__ == "__main__":
    main()