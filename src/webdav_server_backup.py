"""
WebDAV Server Component for InstantTransmission
Serves the user's Public folder via WebDAV protocol
"""

import os
import logging
import threading
from pathlib import Path
from wsgidav.wsgidav_app import WsgiDAVApp
from wsgidav.fs_dav_provider import FilesystemProvider
from cheroot.wsgi import Server as WSGIServer

class WebDAVServer:
    """WebDAV server for sharing the Public folder"""
    
    def __init__(self, port=8080):
        self.logger = logging.getLogger("WebDAV")
        self.port = port
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
    
    def _create_wsgidav_config(self):
        """Create WsgiDAV configuration"""
        provider = FilesystemProvider(self.public_folder, readonly=True) # Set to read-only

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
            # Consider a more robust middleware stack if advanced features are needed
            "middleware_stack": [
                "wsgidav.error_printer.ErrorPrinter",
                # "wsgidav.http_authenticator.HTTPAuthenticator", # Authentication disabled
                "wsgidav.request_resolver.RequestResolver",
            ],
            # Authentication: No authentication by default for ease of local sharing.
            # To enable authentication, configure http_authenticator and a domain_controller.
            "simple_dc": { 
                "user_mapping": {"*": True} # Allow all users (no auth)
            },
            "http_authenticator": {
                "accept_basic": False,
                "accept_digest": False,
                "default_to_digest": False,
                # "trusted_auth_header": None # For reverse proxy auth
            },            # Other options to consider for security:
            # "enable_expect100": True,
            # "re_encode_path_info": None, # Path encoding handling
        }
        return config
    
    def start(self):
        """Start the WebDAV server"""
        try:
            config = self._create_wsgidav_config()
            
            app = WsgiDAVApp(config)
            
            # Use Cheroot for high-performance, multi-threaded serving
            # This should significantly improve transfer speeds compared to wsgiref
            self.server = WSGIServer(
                bind_addr=("0.0.0.0", self.port),
                wsgi_app=app,
                numthreads=10,  # Allow 10 concurrent connections
                timeout=60      # 60 second timeout
            )
            
            self.logger.info(f"Starting Cheroot WebDAV server on 0.0.0.0:{self.port} (read-only)")
            
            # Run the server in a separate thread so it doesn't block the main app
            self.server_thread = threading.Thread(target=self.server.start)
            self.server_thread.daemon = True # Ensure thread exits when main app exits
            self.server_thread.start()
            self.logger.info(f"WebDAV server is running in a background thread with Cheroot.")

        except Exception as e:
            self.logger.error(f"Failed to start WebDAV server: {e}")
            raise
      def stop(self):
        """Stop the WebDAV server"""
        if self.server:
            self.logger.info("Stopping WebDAV server...")
            try:
                self.server.stop() # Cheroot uses stop() instead of shutdown()
                if self.server_thread and self.server_thread.is_alive():
                    self.server_thread.join(timeout=5) # Wait for thread to finish
                self.logger.info("WebDAV server stopped.")
            except Exception as e:
                self.logger.error(f"Error stopping WebDAV server: {e}")
            finally:
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