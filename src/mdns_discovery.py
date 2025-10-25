"""
mDNS Discovery Component for InstantTransmission
Handles service registration and peer discovery using Zeroconf
"""

import logging
import socket
import threading
import time
from zeroconf import ServiceInfo, Zeroconf, ServiceListener
import netifaces
import os # Added for path manipulation
from plyer import notification # Added import

class MDNSServiceListener(ServiceListener):
    """Listener for mDNS service events"""
    
    def __init__(self, on_peer_discovered, on_peer_removed, local_computer_name): # Added local_computer_name
        self.logger = logging.getLogger("MDNSListener")
        self.on_peer_discovered = on_peer_discovered
        self.on_peer_removed = on_peer_removed
        self.discovered_services = {}
        self.local_computer_name = local_computer_name # Store local computer name

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Called when a service is added"""
        self.logger.info(f"Service added: {name}")
        
        # Get service info
        info = zc.get_service_info(type_, name)
        if info:
            # Extract peer information
            # name is like "InstantTransmission-MyPC._webdav._tcp.local."
            peer_service_name_part = name.split('.')[0] # Corrected: "InstantTransmission-MyPC"
            
            # Don\'t discover or notify about ourselves
            if peer_service_name_part == f"InstantTransmission-{self.local_computer_name}":
                self.logger.info(f"Ignoring own service: {name}")
                return

            if not peer_service_name_part.startswith("InstantTransmission-"):
                self.logger.info(f"Ignoring non-InstantTransmission service: {name}")
                return
            
            peer_name_display = peer_service_name_part.replace("InstantTransmission-", "") # "MyPC"
            ip_address = socket.inet_ntoa(info.addresses[0]) if info.addresses else "N/A"
            port = info.port if info.port is not None else 0
                            
            if name not in self.discovered_services: # Only notify for new discoveries
                self.discovered_services[name] = info
                self.on_peer_discovered(peer_service_name_part, ip_address, port) # Use peer_service_name_part for consistency
                try:
                    notification_title = "Instant Transmission"
                    notification_message = f"'{peer_name_display}' is now available for file sharing."
                    app_icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'icon.ico')
                    if not os.path.exists(app_icon_path):
                        self.logger.warning(f"Icon file not found at {app_icon_path}, using default notification icon.")
                        app_icon_path = '' # Plyer will use a default icon

                    notification.notify(
                        title=notification_title,
                        message=notification_message,
                        app_name="Instant Transmission",
                        app_icon=app_icon_path, # Path to .ico file
                        timeout=10  # Notification timeout in seconds
                    )
                    self.logger.info(f"Sent notification for discovered peer: {peer_name_display}")
                except Exception as e:
                    self.logger.error(f"Failed to send notification for {peer_name_display}: {e}")
            else:
                # Service already known, might be an update, re-add if necessary
                self.discovered_services[name] = info 
                # Optionally, call on_peer_discovered if you want to refresh existing entries
                # self.on_peer_discovered(peer_service_name_part, ip_address, port)


    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Called when a service is removed"""
        self.logger.info(f"Service removed: {name}")
        
        if name in self.discovered_services:
            peer_service_name_part = name.split('.')[0] # Corrected
            del self.discovered_services[name]
            self.on_peer_removed(peer_service_name_part) # Use peer_service_name_part
    
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Called when a service is updated"""
        self.logger.info(f"Service updated: {name}")
        # Treat update as remove + add
        self.remove_service(zc, type_, name)
        self.add_service(zc, type_, name)

class MDNSDiscovery:
    """mDNS service registration and discovery"""
    
    def __init__(self, on_peer_discovered, on_peer_removed, port=8080):
        self.logger = logging.getLogger("MDNSDiscovery")
        self.port = port
        self.on_peer_discovered = on_peer_discovered
        self.on_peer_removed = on_peer_removed
        self.local_computer_name = self._get_computer_name() # Get local computer name once
        
        self.zeroconf = None
        self.service_info = None
        self.listener = None
        self.service_type = "_webdav._tcp.local."
        
    def _get_local_ip(self):
        """Get the primary local IP address"""
        try:
            # Try to get the IP by connecting to a remote address
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except:
            # Fallback: get from network interfaces
            try:
                for interface in netifaces.interfaces():
                    addrs = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET in addrs:
                        for addr_info in addrs[netifaces.AF_INET]:
                            ip = addr_info.get('addr')
                            if ip and not ip.startswith('127.') and not ip.startswith('169.254'):
                                return ip
            except:
                pass
            
            return "127.0.0.1"
    
    def _get_computer_name(self):
        """Get computer name for service identification"""
        import os
        return os.environ.get('COMPUTERNAME', 'Unknown')
    
    def start(self):
        """Start mDNS service registration and discovery"""
        try:
            self.zeroconf = Zeroconf()
            
            # Register our service
            self._register_service()
            
            # Start listening for other services
            self._start_discovery()
            
            self.logger.info("mDNS discovery started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start mDNS discovery: {e}")
            raise
    
    def _register_service(self):
        """Register our WebDAV service"""
        assert self.zeroconf is not None, "Zeroconf must be initialized before registering a service."
        try:
            local_ip = self._get_local_ip()
            computer_name = self._get_computer_name()
            service_name = f"InstantTransmission-{computer_name}.{self.service_type}"
            
            # Create service info
            self.service_info = ServiceInfo(
                self.service_type,
                service_name,
                addresses=[socket.inet_aton(local_ip)],
                port=self.port,
                properties={
                    'path': '/',
                    'version': '1.0',
                    'app': 'InstantTransmission'
                },
                server=f"{computer_name}.local."
            )
            
            # Register the service
            self.zeroconf.register_service(self.service_info)
            self.logger.info(f"Registered service: {service_name} at {local_ip}:{self.port}")
            
        except Exception as e:
            self.logger.error(f"Failed to register service: {e}")
            raise
    
    def _start_discovery(self):
        """Start discovering other InstantTransmission services"""
        assert self.zeroconf is not None, "Zeroconf must be initialized before starting discovery."
        try:
            self.listener = MDNSServiceListener(
                self.on_peer_discovered,
                self.on_peer_removed,
                self.local_computer_name # Pass local computer name
            )
            
            self.zeroconf.add_service_listener(self.service_type, self.listener)
            self.logger.info(f"Started browsing for {self.service_type} services")
            
        except Exception as e:
            self.logger.error(f"Failed to start service discovery: {e}")
            raise
    
    def trigger_peer_rediscovery(self):
        """Triggers a re-discovery of peers by re-attaching the service listener."""
        if self.zeroconf and self.listener and self.service_type:
            self.logger.info("Attempting to trigger peer rediscovery.")
            try:
                # Detach the current listener
                self.zeroconf.remove_service_listener(self.listener)
                self.logger.info(f"Removed service listener for {self.service_type} for rediscovery.")
                
                # Re-attach the listener. This should prompt zeroconf to send
                # add_service notifications for all currently known services.
                self.zeroconf.add_service_listener(self.service_type, self.listener)
                self.logger.info(f"Re-added service listener for {self.service_type} for rediscovery.")
            except Exception as e:
                self.logger.error(f"Error during peer rediscovery: {e}")
        else:
            self.logger.warning("Cannot trigger peer rediscovery: Zeroconf, listener, or service_type not initialized.")

    def stop(self):
        """Stop mDNS service and discovery"""
        if self.zeroconf:
            try:
                # Unregister our service
                if self.service_info:
                    self.zeroconf.unregister_service(self.service_info)
                    self.logger.info("Unregistered our service")
                  # Remove listener
                if self.listener:
                    self.zeroconf.remove_service_listener(self.listener)
                    self.logger.info("Removed service listener")
                
                # Close zeroconf
                self.zeroconf.close()
                self.logger.info("mDNS discovery stopped")
                
            except Exception as e:
                self.logger.error(f"Error stopping mDNS discovery: {e}")
    
    def get_discovered_peers(self):
        """Get currently discovered peers"""
        if self.listener:
            return self.listener.discovered_services
        return {}
