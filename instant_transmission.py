#!/usr/bin/env python3
"""
InstantTransmission - Zero-configuration local file sharing utility for Windows
Main entry point for the application
"""

import os
import sys
import threading
import time
import logging
from pathlib import Path

# Import our custom modules (will create these)
from src.webdav_server import WebDAVServer
from src.mdns_discovery import MDNSDiscovery
from src.system_tray import SystemTrayApp
from src.file_explorer import FileExplorerGUI
from src.password_manager import PasswordManager
from src.admin_utils import ensure_admin_privileges, setup_firewall_rules, setup_public_folder_permissions, create_public_folder_if_needed

def setup_logging():
    """Setup logging for the application"""
    log_dir = Path.home() / "AppData" / "Local" / "InstantTransmission"
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "instant_transmission.log"),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger("InstantTransmission")

class InstantTransmissionApp:
    """Main application coordinator"""
      def __init__(self):
        self.logger = setup_logging()
        self.logger.info("Starting InstantTransmission...")
        
        # Core components
        self.password_manager = PasswordManager()
        self.webdav_server: Optional[WebDAVServer] = None
        self.mdns_discovery: Optional[MDNSDiscovery] = None
        self.system_tray: Optional[SystemTrayApp] = None
        self.discovered_peers = {}
        
        # Threading
        self.shutdown_event = threading.Event() # Corrected: ensure this is on its own line
        
    def initialize(self):
        """Initialize all application components"""
        try:
            # Try to setup admin-required features, but don't fail if we can't
            try:
                if ensure_admin_privileges():
                    self.logger.info("Setting up firewall rules and permissions...")
                    setup_firewall_rules()
                    setup_public_folder_permissions()
                else:
                    self.logger.warning("Running without admin privileges - firewall rules may need manual setup")
            except SystemExit:
                # ensure_admin_privileges() called sys.exit() to restart with admin privileges
                # This is expected behavior, let it happen
                raise
            except Exception as e:
                self.logger.warning(f"Could not setup admin features: {e}")
            
            create_public_folder_if_needed()
              # Initialize WebDAV server
            self.logger.info("Initializing WebDAV server...")
            self.webdav_server = WebDAVServer(password_manager=self.password_manager) # Port is set within WebDAVServer's __init__
            
            # Initialize mDNS discovery
            self.logger.info("Initializing mDNS discovery...")
            if not self.webdav_server:
                self.logger.error("WebDAV server failed to initialize. Cannot start mDNS discovery.")
                return False
            self.mdns_discovery = MDNSDiscovery(self.on_peer_discovered, self.on_peer_removed, port=self.webdav_server.port)
              # Initialize system tray
            self.logger.info("Initializing system tray...")
            if not self.mdns_discovery:
                self.logger.error("mDNS discovery failed to initialize. Cannot start system tray.")
                return False
            self.system_tray = SystemTrayApp(
                self.discovered_peers, 
                self.open_file_explorer, 
                self.shutdown, 
                mdns_discovery_instance=self.mdns_discovery, # Pass the instance
                password_manager=self.password_manager
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize application: {e}")
            # Ensure components are None if initialization fails midway
            self.webdav_server = None
            self.mdns_discovery = None
            self.system_tray = None
            return False
    
    def start(self):
        """Start all application services"""
        try:
            # Start WebDAV server in background thread
            if self.webdav_server:
                self.logger.info("Starting WebDAV server...")
                webdav_thread = threading.Thread(target=self.webdav_server.start, daemon=True)
                webdav_thread.start()
                time.sleep(2) # Give WebDAV server time to start
            else:
                self.logger.error("WebDAV server not initialized. Cannot start.")
                self.shutdown()
                return

            # Start mDNS discovery
            if self.mdns_discovery:
                self.logger.info("Starting mDNS discovery...")
                self.mdns_discovery.start()
            else:
                self.logger.error("mDNS discovery not initialized. Cannot start.")
                self.shutdown()
                return
            
            # Start system tray (blocking call)
            if self.system_tray:
                self.logger.info("Starting system tray...")
                self.system_tray.run() # This blocks until exit
            else:
                self.logger.error("System tray not initialized. Cannot start.")
                self.shutdown()
                return
            
        except Exception as e:
            self.logger.error(f"Error starting application: {e}")
            self.shutdown()
    
    def on_peer_discovered(self, name, ip, port):
        """Called when a new peer is discovered"""
        self.logger.info(f"Discovered peer: {name} at {ip}:{port}")
        self.discovered_peers[name] = {"ip": ip, "port": port}
        
        if self.system_tray:
            self.system_tray.update_discovered_peers(self.discovered_peers)
    
    def on_peer_removed(self, name):
        """Called when a peer is removed"""
        self.logger.info(f"Peer removed: {name}")
        if name in self.discovered_peers:
            del self.discovered_peers[name]
            
        if self.system_tray:
            self.system_tray.update_discovered_peers(self.discovered_peers)
    
    def open_file_explorer(self, peer_name):
        """Open file explorer for a specific peer"""
        if peer_name not in self.discovered_peers:
            self.logger.error(f"Peer {peer_name} not found")
            return
            
        peer_info = self.discovered_peers[peer_name]
        base_url = f"http://{peer_info['ip']}:{peer_info['port']}"
        
        # Open file explorer in new thread to avoid blocking
        explorer_thread = threading.Thread(
            target=lambda: FileExplorerGUI(peer_name, base_url).run(),
            daemon=True
        )
        explorer_thread.start()
    
    def shutdown(self):
        """Gracefully shutdown all services"""
        self.logger.info("Shutting down InstantTransmission...")
        
        self.shutdown_event.set() # Signal other threads if they are waiting on this
        
        # Stop system tray first if it's running and has a stop method
        # pystray's icon.stop() is usually called from its own menu's exit action.
        # If self.system_tray.run() is blocking, it will exit when its icon is stopped.

        if self.mdns_discovery:
            self.logger.info("Stopping mDNS discovery...")
            self.mdns_discovery.stop()
            
        if self.webdav_server:
            self.logger.info("Stopping WebDAV server...")
            self.webdav_server.stop()
        
        self.logger.info("Shutdown complete.")
        # sys.exit(0) # The application will exit naturally after system_tray.run() finishes.
                      # Or if called from an error path, sys.exit might be appropriate.
                      # For now, let main handle exit.

def main():
    """Main entry point"""
    app = InstantTransmissionApp()
    
    if not app.initialize():
        # Logger might not be fully set up if setup_logging itself failed,
        # but app.logger should exist from __init__.
        app.logger.error("Failed to initialize InstantTransmission. Exiting.")
        sys.exit(1)
    
    try:
        app.start() # This will block until system_tray exits
    except KeyboardInterrupt:
        app.logger.info("Keyboard interrupt received.")
        app.shutdown()
    except Exception as e:
        app.logger.error(f"Unexpected error in main execution: {e}", exc_info=True)
        app.shutdown()
    finally:
        app.logger.info("Application has exited.")
        # Ensure sys.exit is called if shutdown wasn't, or if shutdown doesn't exit.
        # However, pystray's exit should lead to the end of app.start(), then main finishes.
        # If shutdown is called due to an error, it should handle exit.
        # Let's ensure a clean exit.
        if not app.shutdown_event.is_set(): # If shutdown wasn't called explicitly
             app.shutdown() # Try a graceful shutdown
        sys.exit(0) # Ensure exit

if __name__ == "__main__":
    # Add type hints for core components for better linting if not already there
    from typing import Optional 
    from src.webdav_server import WebDAVServer
    from src.mdns_discovery import MDNSDiscovery
    from src.system_tray import SystemTrayApp

    main()
