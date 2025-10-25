"""
WebDAV Server Component for InstantTransmission
Serves the user's Public folder via WebDAV protocol
"""

import os
import logging
import threading
# import wsgiref.simple_server # No longer needed
from pathlib import Path
from wsgidav.wsgidav_app import WsgiDAVApp
from wsgidav.fs_dav_provider import FilesystemProvider
from waitress import serve # Import serve from waitress
from .password_manager import PasswordManager

class WebDAVServer:
    """WebDAV server for sharing the Public folder"""
    
    def __init__(self, port=8080, password_manager=None):
        self.logger = logging.getLogger("WebDAV")
        self.port = port
        self.password_manager = password_manager or PasswordManager()
        self.public_folder = self._get_public_folder()
        self.server = None
        self.server_thread = None
        
        self.logger.info(f"WebDAV server will serve: {self.public_folder}")
    
    def _get_public_folder(self):
        """Get the user's Public folder path"""
        # Windows Public folder is usually C:\Users\Public or user-specific
        public_paths = [
            Path.home() / "Public",
            Path("C:/Users/Public"),
            Path.home() / "Documents"  # Fallback
        ]
        
        for path in public_paths:
            if path.exists():
                self.logger.info(f"Using Public folder: {path}")
                return str(path.resolve())
        
        # Create Public folder if none exists
        public_folder = Path.home() / "Public"
        public_folder.mkdir(parents=True, exist_ok=True)  # Ensured proper indentation and added parents=True
        self.logger.info(f"Created Public folder: {public_folder}")
        return str(public_folder.resolve())
    
    def _get_plain_password(self):
        """Get plain text password for current session (insecure but needed for SimpleDomainController)"""
        # This is a limitation of WsgiDAV's SimpleDomainController - it needs plaintext passwords
        # In a production environment, you'd use a more sophisticated domain controller
        return getattr(self, '_temp_password', 'defaultpass')
    
    def set_session_password(self, password: str):
        """Set the password for current session (used during configuration)"""
        self._temp_password = password    def _create_wsgidav_config(self):
        """Create WsgiDAV configuration"""
        provider = FilesystemProvider(self.public_folder, readonly=False) # Enable read-write for better performance

        # Check if password protection is enabled
        auth_enabled = self.password_manager.is_enabled()
        
        config = {
            "host": "0.0.0.0", # WsgiDAV internal host, actual server binds below
            "port": self.port,
            "provider_mapping": {
                "/": provider # Use the read-only provider
            },
            "verbose": 1, # Minimal logging for production, adjust for debugging
            "logging": {
                "enable_loggers": [] # Disable WsgiDAV's verbose logging by default
            },
            "property_manager": None, # Use default in-memory
            "lock_storage": None,     # Use default in-memory
        }
        
        if auth_enabled:
            # Enable authentication
            config["middleware_stack"] = [
                "wsgidav.error_printer.ErrorPrinter",
                "wsgidav.http_authenticator.HTTPAuthenticator",
                "wsgidav.request_resolver.RequestResolver",
            ]
            
            # Simple domain controller for basic auth
            config["simple_dc"] = {
                "user_mapping": {
                    "/": {
                        self.password_manager.get_username(): {
                            "password": self._get_plain_password(),
                            "description": "InstantTransmission User",
                            "roles": []
                        }
                    }
                }
            }
            
            config["http_authenticator"] = {
                "accept_basic": True,
                "accept_digest": False,
                "default_to_digest": False,
                "domain_controller": "wsgidav.domain_controller.SimpleDomainController"
            }
            
            self.logger.info("WebDAV authentication enabled")
        else:
            # No authentication
            config["middleware_stack"] = [
                "wsgidav.error_printer.ErrorPrinter",
                "wsgidav.request_resolver.RequestResolver",
            ]
            
            config["simple_dc"] = { 
                "user_mapping": {"*": True} # Allow all users (no auth)
            }
            
            config["http_authenticator"] = {
                "accept_basic": False,
                "accept_digest": False,
                "default_to_digest": False,
            }
            
            self.logger.info("WebDAV authentication disabled")
        
        return config
    
    def start(self):
        """Start the WebDAV server"""
        try:
            config = self._create_wsgidav_config()
            
            # WsgiDAVApp is a WSGI application, so this should be fine.
            # The type error might be a linter/type checker issue if WsgiDAVApp
            # doesn't perfectly match the WSGIApplication protocol in a way the checker expects.
            # However, it's designed to be a WSGI app.
            wsgi_app = WsgiDAVApp(config)
            
            self.logger.info(f"Starting WebDAV server on 0.0.0.0:{self.port} (read-only) using Waitress")            # Run the Waitress server in a separate thread
            def _serve():
                # Explicitly pass the wsgi_app object to waitress with optimized settings
                serve(wsgi_app, host="0.0.0.0", port=self.port, 
                     threads=32,  # Increase thread count for better performance
                     connection_limit=1000,  # Allow more concurrent connections
                     cleanup_interval=10,  # Faster cleanup
                     channel_timeout=300)  # 5 minute timeout for large transfers

            self.server_thread = threading.Thread(target=_serve)
            self.server_thread.daemon = True 
            self.server_thread.start()
            self.logger.info(f"WebDAV server (Waitress) is running in a background thread.")

        except Exception as e:
            self.logger.error(f"Failed to start WebDAV server: {e}")
            raise
    
    def stop(self):
        """Stop the WebDAV server"""
        if self.server_thread and self.server_thread.is_alive():
            self.logger.info("Stopping WebDAV server (Waitress)... (Note: Waitress runs as a daemon thread)")
            self.logger.info("WebDAV server (Waitress) will stop when the application exits.")
        self.server = None 
        self.server_thread = None
    
    def get_local_urls(self):
        """Get all local URLs where the server is accessible"""
        import netifaces
        urls = []
        
        try:
            # Get all network interfaces
            for interface in netifaces.interfaces():
                try:
                    addrs = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET in addrs:
                        for addr_info in addrs[netifaces.AF_INET]:
                            ip = addr_info.get('addr')
                            if ip and not ip.startswith('127.'):
                                urls.append(f"http://{ip}:{self.port}")
                except:
                    continue
        except Exception as e:
            self.logger.warning(f"Could not enumerate network interfaces: {e}")
            urls.append(f"http://localhost:{self.port}")
        
        return urls