#!/usr/bin/env python3
"""
HomeKit Connector - Main entry point
Launches supervisord to manage multiple processes
"""

import os
import sys
import signal
import subprocess
import logging
from pathlib import Path

# Add shared to path
sys.path.insert(0, '/app/shared')
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'shared'))

logger = logging.getLogger(__name__)

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)

def main():
    """Main entry point - launch supervisord"""
    # Setup logging
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Get mode and instance name
    mode = os.getenv('MODE', 'production')
    instance_name = os.getenv('INSTANCE_NAME')

    if not instance_name:
        logger.error("INSTANCE_NAME environment variable not set")
        sys.exit(1)

    logger.info(f"Starting HomeKit Connector for instance '{instance_name}' in {mode} mode")

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Launch supervisord
    logger.info("Launching supervisord to manage processes...")

    try:
        # Start supervisord in foreground
        supervisor_config = '/app/supervisord.conf'

        if not os.path.exists(supervisor_config):
            logger.error(f"Supervisord config not found: {supervisor_config}")
            sys.exit(1)

        # Run supervisord
        subprocess.run(
            ['supervisord', '-c', supervisor_config],
            check=True
        )

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except subprocess.CalledProcessError as e:
        logger.error(f"Supervisord failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
