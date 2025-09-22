#!/usr/bin/env python3
"""
Main entry point for Xiaomi MiIO Connector
"""

import sys
import os
import logging
import signal
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from connectors.xiaomi_miio.connector import Connector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global connector instance
connector = None


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global connector
    logger.info(f"Received signal {signum}, shutting down...")
    if connector:
        connector.stop()
    sys.exit(0)


def main():
    """Main entry point"""
    global connector
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Get instance name from environment or arguments
    instance_name = os.getenv('INSTANCE_NAME')
    if not instance_name and len(sys.argv) > 1:
        instance_name = sys.argv[1]
    
    if not instance_name:
        logger.error("No instance name provided. Use INSTANCE_NAME env var or pass as argument")
        sys.exit(1)
    
    # Get config path
    config_path = os.getenv('CONFIG_PATH')
    if not config_path:
        # Try standard locations
        config_path = f"/app/instances/{instance_name}.json"
        if not os.path.exists(config_path):
            config_path = f"instances/{instance_name}.json"
    
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)
    
    logger.info(f"Starting Xiaomi MiIO Connector for instance: {instance_name}")
    logger.info(f"Using configuration: {config_path}")
    
    try:
        # Create and start connector
        connector = Connector(config_path=config_path, instance_name=instance_name)
        
        if not connector.start():
            logger.error("Failed to start connector")
            sys.exit(1)
        
        logger.info("Connector started successfully")
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if connector:
            connector.stop()
        logger.info("Connector stopped")


if __name__ == "__main__":
    main()
