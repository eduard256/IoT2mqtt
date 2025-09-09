#!/usr/bin/env python3
"""
Template Connector - Main entry point
This file handles initialization and hot reload in development mode
"""

import os
import sys
import signal
import time
import importlib
import logging
from pathlib import Path

# Add shared to path (for Docker volume mount)
sys.path.insert(0, '/app/shared')
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'shared'))

from connector import Connector

logger = logging.getLogger(__name__)

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    if 'connector' in globals():
        connector.stop()
    sys.exit(0)

def main():
    """Main entry point"""
    # Setup logging
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Get mode (production or development)
    mode = os.getenv('MODE', 'production')
    instance_name = os.getenv('INSTANCE_NAME')
    
    if not instance_name:
        logger.error("INSTANCE_NAME environment variable not set")
        sys.exit(1)
    
    logger.info(f"Starting Template Connector for instance '{instance_name}' in {mode} mode")
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    if mode == 'development':
        # Development mode with hot reload
        logger.info("Hot reload enabled - watching for changes in connector.py")
        
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
            
            class ReloadHandler(FileSystemEventHandler):
                def __init__(self):
                    self.connector = None
                    self.reload_connector()
                
                def on_modified(self, event):
                    if event.src_path.endswith('connector.py'):
                        logger.info("Detected change in connector.py, reloading...")
                        self.reload_connector()
                
                def reload_connector(self):
                    try:
                        # Stop existing connector
                        if self.connector:
                            self.connector.stop()
                        
                        # Reload module
                        if 'connector' in sys.modules:
                            importlib.reload(sys.modules['connector'])
                        else:
                            import connector
                        
                        # Create new instance
                        from connector import Connector
                        self.connector = Connector(instance_name=instance_name)
                        self.connector.start()
                        
                        logger.info("Connector reloaded successfully")
                        
                    except Exception as e:
                        logger.error(f"Failed to reload connector: {e}")
                        import traceback
                        traceback.print_exc()
                
                def stop(self):
                    if self.connector:
                        self.connector.stop()
            
            # Setup file watcher
            handler = ReloadHandler()
            observer = Observer()
            observer.schedule(handler, path='.', recursive=False)
            observer.start()
            
            # Keep running
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                observer.stop()
                handler.stop()
            
            observer.join()
            
        except ImportError:
            logger.warning("Watchdog not available, falling back to production mode")
            mode = 'production'
    
    if mode == 'production':
        # Production mode - simple and stable
        logger.info("Running in production mode")
        
        try:
            # Create and run connector
            connector = Connector(instance_name=instance_name)
            connector.run_forever()
            
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    main()