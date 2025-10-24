#!/usr/bin/env python3
"""
HomeKit Connector Entry Point
"""

import logging
import sys
from connector import Connector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


if __name__ == '__main__':
    logger.info("Starting HomeKit Connector...")

    try:
        # Create and start connector
        connector = Connector()
        connector.run_forever()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
