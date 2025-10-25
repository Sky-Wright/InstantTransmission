"""
System Tray Component for InstantTransmission
Provides system tray icon and context menu for easy access
"""

import logging
import os
import subprocess
import threading
from pathlib import Path
from PIL import Image, ImageDraw
import pystray
from typing import TYPE_CHECKING, Optional, Any # Import Any
from .password_manager import PasswordManager

if TYPE_CHECKING:
    from src.mdns_discovery import MDNSDiscovery # Import for type hinting
    # This helps with type checking without causing circular imports at runtime

class SystemTrayApp:
    """System tray interface for InstantTransmission"""
    
    def __init__(self, discovered_peers, open_file_explorer_callback, shutdown_callback, mdns_discovery_instance: 'Optional[MDNSDiscovery]' = None, password_manager: Optional[PasswordManager] = None):
        self.logger = logging.getLogger("SystemTray")
        self.discovered_peers = discovered_peers
        self.open_file_explorer_callback = open_file_explorer_callback
        self.shutdown_callback = shutdown_callback
        self.mdns_discovery_instance = mdns_discovery_instance # Store MDNSDiscovery instance
        self.password_manager = password_manager or PasswordManager()
        
        self.icon: Optional[Any] = None # Use Any to bypass pystray.Icon type issue for now
        self.menu_items = []
        
    def _create_icon(self):
        """Load the icon.ico file for the system tray."""
        try:
            # Determine the path to icon.ico relative to this script file (src/system_tray.py)
            # The icon.ico is in the project root, so one level up from the 'src' directory.
            icon_path = Path(__file__).resolve().parent.parent / "icon.ico"
            if icon_path.exists():
                self.logger.info(f"Loading tray icon from: {icon_path}")
                return Image.open(icon_path)
            else:
                self.logger.warning(f"Tray icon file not found at {icon_path}. Creating default icon.")
                return self._create_default_fallback_icon()
        except Exception as e:
            self.logger.error(f"Failed to load tray icon: {e}. Creating default icon.")
            return self._create_default_fallback_icon()

    def _create_default_fallback_icon(self):
        """Create a simple fallback icon if icon.ico is not found."""
        # This is the original icon creation logic
        image = Image.new('RGB', (64, 64), color='blue')
        draw = ImageDraw.Draw(image)
        draw.rectangle([8, 8, 56, 56], outline='white', width=3)
        draw.rectangle([16, 16, 48, 48], fill='lightblue')
        # Add IT letters
        draw.text((32, 32), "IT", fill='white', anchor="mm") # Centered text
        
        return image
    
    def _open_public_folder(self):
        """Open the local Public folder in Windows Explorer"""
        try:
            # Get the Public folder path
            public_paths = [
                Path.home() / "Public",
                Path("C:/Users/Public"),
                Path.home() / "Documents"
            ]
            
            public_folder = None
            for path in public_paths:
                if path.exists():
                    public_folder = path
                    break
            
            if public_folder:
                # Open in Windows Explorer
                subprocess.Popen(f'explorer "{public_folder}"')
                self.logger.info(f"Opened Public folder: {public_folder}")
            else:
                self.logger.error("Could not find Public folder")
                
        except Exception as e:
            self.logger.error(f"Failed to open Public folder: {e}")
    
    def _create_peer_menu_item(self, peer_name):
        """Create a menu item for a discovered peer"""
        def open_peer():
            self.open_file_explorer_callback(peer_name)
        
        return pystray.MenuItem(
            f"📁 {peer_name}",
            open_peer
        )
    
    def _show_password_settings(self):
        """Show password protection settings dialog"""
        try:
            import tkinter as tk
            import sv_ttk
            
            # Create a temporary root window for the dialog
            root = tk.Tk()
            root.withdraw()  # Hide the root window
            
            # Apply dark theme
            try:
                sv_ttk.set_theme("dark")
            except:
                pass  # Continue without theme if it fails
            
            # Show password dialog
            self.password_manager.show_password_dialog(root)
            
            # Clean up
            root.destroy()
            
            # Log the result
            if self.password_manager.is_enabled():
                self.logger.info("Password protection enabled")
            else:
                self.logger.info("Password protection disabled")
                
        except Exception as e:
            self.logger.error(f"Error showing password settings: {e}")
    
    def _get_password_status_text(self):
        """Get the current password protection status text"""
        if self.password_manager.is_enabled():
            return "🔒 Password: ON"
        else:
            return "🔓 Password: OFF"

    def _create_menu(self):
        """Create the context menu for the system tray"""
        menu_items = [
            pystray.MenuItem("📂 Open My Public Folder", self._open_public_folder),
            pystray.MenuItem("🔄 Refresh Peers", self._trigger_refresh_peers), # Changed to call _trigger_refresh_peers
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self._get_password_status_text(), self._show_password_settings),
            pystray.Menu.SEPARATOR,
        ]
        
        # Add discovered peers
        if self.discovered_peers:
            menu_items.append(pystray.MenuItem("🌐 Discovered Peers:", None, enabled=False))
            for peer_name in sorted(self.discovered_peers.keys()):
                menu_items.append(self._create_peer_menu_item(peer_name))
            menu_items.append(pystray.Menu.SEPARATOR)
        else:
            menu_items.append(pystray.MenuItem("🔍 No peers discovered yet", None, enabled=False))
            menu_items.append(pystray.Menu.SEPARATOR)
        
        # Add exit option
        menu_items.append(pystray.MenuItem("❌ Exit", self._exit_application))
        
        return pystray.Menu(*menu_items)
    
    def _exit_application(self):
        """Exit the application"""
        self.logger.info("Exit requested from system tray")
        if self.icon: # Check if icon exists before trying to stop
            self.icon.stop()
        self.shutdown_callback()

    def _trigger_refresh_peers(self):
        """Calls the MDNSDiscovery instance to re-scan for peers."""
        if self.mdns_discovery_instance:
            self.logger.info("Triggering peer rediscovery via MDNSDiscovery instance.")
            self.mdns_discovery_instance.trigger_peer_rediscovery()
            # The MDNSDiscovery component will call update_discovered_peers on the tray app,
            # which in turn calls _refresh_peer_list_display.
        else:
            self.logger.warning("MDNSDiscovery instance not available, cannot trigger peer refresh.")

    def _refresh_peer_list_display(self):
        """Re-generates and updates the system tray menu to reflect current peers."""
        if self.icon: 
            self.logger.info("Refreshing system tray menu display.")
            # Re-create the menu structure and tell pystray to update
            new_menu = self._create_menu()
            # Ensure self.icon is a pystray.Icon instance before accessing .menu
            if isinstance(self.icon, pystray.Icon):
                self.icon.menu = new_menu
            else:
                self.logger.warning("Icon object is not a pystray.Icon instance, cannot set menu.")
        else:
            self.logger.warning("Tray icon object not found, cannot refresh menu.")

    def update_discovered_peers(self, discovered_peers):
        """Update the list of discovered peers and refresh the tray menu."""
        self.discovered_peers = discovered_peers
        self._refresh_peer_list_display() # Refresh menu when peers change

    def run(self):
        """Create and run the system tray icon."""
        try:
            # Ensure icon image is created first
            icon_image = self._create_icon() 
            if not icon_image:
                self.logger.error("Failed to create icon image. Tray icon cannot start.")
                return

            # Create the pystray.Icon object and store it in self.icon
            self.icon = pystray.Icon(
                "InstantTransmission",
                icon=icon_image,
                title="InstantTransmission",
                menu=self._create_menu() 
            )
            self.logger.info("System tray icon created. Running...")
            if self.icon: # Ensure icon was created before running
                self.icon.run() # This is a blocking call
            self.logger.info("System tray icon stopped.")
            
        except Exception as e:
            self.logger.error(f"Failed to run system tray icon: {e}")

# Example of how this might be run in a thread from the main application:
# if __name__ == '__main__':
#     logging.basicConfig(level=logging.INFO)
#     def open_explorer_mock(peer_name):
#         print(f"Opening explorer for {peer_name}")
#     def shutdown_mock():
#         print("Shutting down")
#         # In a real app, this would signal the tray icon's run loop to stop if needed,
#         # or handle other cleanup.
#         # For pystray, icon.stop() called from _exit_application should handle it.

#     peers = {"Peer1": "192.168.1.100", "Peer2": "192.168.1.101"}
#     tray_app = SystemTrayApp(peers, open_explorer_mock, shutdown_mock)
    
#     # To run in a separate thread:
#     tray_thread = threading.Thread(target=tray_app.run, daemon=True)
#     tray_thread.start()
    
#     # Keep main thread alive for testing, or let application logic run
#     try:
#         while True:
#             time.sleep(1)
#             # Simulate peer list update
#             # if time.time() % 20 < 1: # Roughly every 20 seconds
#             #     new_peer_name = f"Peer{int(time.time() % 100)}"
#             #     peers[new_peer_name] = "192.168.1.102"
#             #     tray_app.update_discovered_peers(peers) # Update tray menu

#     except KeyboardInterrupt:
#         print("Main app interrupted. Exiting.")
#         if tray_app.icon:
#             tray_app.icon.stop() # Ensure tray icon stops
#         if tray_thread.is_alive():
#             tray_thread.join(timeout=2) # Wait for tray thread to finish
