"""
File Explorer GUI Component for InstantTransmission
Custom Tkinter-based file browser for remote peer access
"""

import logging
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
from urllib.parse import urljoin, quote, unquote
from pathlib import Path
import threading
from xml.etree import ElementTree as ET
import mimetypes
import time
from typing import Optional, List, Tuple, Any
import sv_ttk # Import the new theme library
import json # For saving/loading config
from pathlib import Path # For config file path
from .password_manager import PasswordPromptDialog

CONFIG_DIR = Path.home() / ".InstantTransmission"
CONFIG_FILE = CONFIG_DIR / "file_explorer_config.json"

class FileExplorerGUI:
    """Custom file explorer for browsing remote peers"""
    
    def __init__(self, peer_name: str, base_url: str): # Added type hints for arguments
        self.logger = logging.getLogger("FileExplorer")
        self.peer_name = peer_name
        self.base_url = base_url.rstrip('/')
        self.current_path = "/"
        self.path_history: List[str] = ["/"] 
        self.session = requests.Session()  # Reuse session for authentication
        self.authenticated = False
        self.auth_credentials = None

        # Default UI settings
        self.window_geometry: str = "800x600" 
        self.column_widths: dict[str, int] = {
            "#0": 40,
            "Name": 350,
            "Size": 100,
            "Modified": 150,
            "Type": 120
        }
        self._load_config()
        
        # GUI components
        self.root: Optional[tk.Tk] = None
        self.tree: Optional[ttk.Treeview] = None # Added type hint
        self.status_bar: Optional[ttk.Label] = None # Added type hint
        self.path_label: Optional[ttk.Label] = None # Added type hint
        self.progress_frame: Optional[ttk.Frame] = None # Added type hint
        self.progress_bar: Optional[ttk.Progressbar] = None 
        self.progress_label: Optional[ttk.Label] = None
        self.download_eta_label: Optional[ttk.Label] = None # Added for ETA
        self.download_speed_label: Optional[ttk.Label] = None # Added for speed
          # File operations
        # self.download_folder = Path.home() / "Downloads" / "InstantTransmission" # No longer the primary download target
        # For the "Open Downloads" button, we can keep a default or make it smarter later.
        self._default_downloads_path = Path.home() / "Downloads" / "InstantTransmission"
        self._default_downloads_path.mkdir(parents=True, exist_ok=True)

    def run(self):
        """Start the file explorer GUI"""
        try:
            self.root = tk.Tk()
            self.root.title(f"InstantTransmission - {self.peer_name}")
            
            # Apply loaded or default geometry
            if self.window_geometry:
                try:
                    self.root.geometry(self.window_geometry)
                except tk.TclError as e:
                    self.logger.warning(f"Invalid geometry string '{self.window_geometry}': {e}. Using default.")
                    self.root.geometry("800x600") # Fallback to default

            self._create_gui()
            self._load_directory(self.current_path)
            
            self.root.protocol("WM_DELETE_WINDOW", self._on_close) # Handle window close
            self.root.mainloop()
            
        except Exception as e:
            self.logger.error(f"Failed to start file explorer: {e}")
            if self.root: # Check if root was created before trying to use messagebox
                messagebox.showerror("Error", f"Failed to start file explorer: {e}")
    
    def _create_gui(self):
        """Create the GUI layout with comprehensive dark mode theme"""
        assert self.root is not None, "self.root must be initialized before calling _create_gui"

        # Set the sv_ttk dark theme
        sv_ttk.set_theme("dark")

        # Remove explicit root background configuration to let sv_ttk handle it
        # self.root.configure(bg=\'#1c1c1c\') 

        # Apply custom dark theme styling AFTER sv_ttk.set_theme
        self._apply_custom_dark_styles()

        # Try to set dark title bar on Windows (remains relevant)
        try:
            import ctypes
            self.root.update_idletasks() 
            hwnd = self.root.winfo_id() 

            if hwnd: 
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                value = ctypes.c_int(1)
                ret = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(value),
                    ctypes.sizeof(value)
                )
                if ret != 0: 
                    if hasattr(self, 'logger') and self.logger:
                        self.logger.warning(f"DwmSetWindowAttribute for dark title bar failed with code {ret}. This is non-critical.")
            else:
                if hasattr(self, 'logger') and self.logger:
                    self.logger.warning("Could not get valid HWND for dark title bar. This is non-critical.")
        except ImportError:
            if hasattr(self, 'logger') and self.logger:
                self.logger.info("ctypes module not available. Cannot set dark title bar.")
        except AttributeError as e_attr:
            if hasattr(self, 'logger') and self.logger:
                self.logger.warning(f"AttributeError while trying to set dark title bar (e.g., root window not ready): {e_attr}. This is non-critical.")
        except Exception as e_dwm:
            if hasattr(self, 'logger') and self.logger:
                self.logger.warning(f"Unexpected error setting dark title bar: {e_dwm}. This is non-critical.")
        
        # Toolbar
        # Use default ttk.Frame, Button, Label as sv_ttk will style them
        toolbar = ttk.Frame(self.root, style='TFrame') # Explicitly apply TFrame style
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="⬅️ Back", command=self._go_back, style='TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🏠 Home", command=self._go_home, style='TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🔄 Refresh", command=self._refresh, style='TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="⬇️ Download", command=self._download_selected, style='TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📁 Open Downloads", command=self._open_downloads, style='TButton').pack(side=tk.LEFT, padx=2)
        
        # Path display
        path_frame = ttk.Frame(self.root, style='TFrame') # Explicitly apply TFrame style
        path_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(path_frame, text="Path:", style='TLabel').pack(side=tk.LEFT)
        self.path_label = ttk.Label(path_frame, text=self.current_path, relief=tk.SUNKEN, style='TLabel') 
        self.path_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # File list
        list_frame = ttk.Frame(self.root, style='TFrame') # Explicitly apply TFrame style
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
          # Treeview for file listing
        columns = ("Name", "Size", "Modified", "Type")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="tree headings", style="Treeview") # Explicitly apply Treeview style
        
        self.tree.heading("#0", text="") 
        self.tree.column("#0", width=self.column_widths.get("#0", 40), minwidth=40, stretch=tk.NO) 
        
        columns = ("Name", "Size", "Modified", "Type") # Ensure columns is defined here
        for col_name in columns: # Use col_name consistently
            self.tree.heading(col_name, text=col_name)
            default_width = 150 # A generic default if key is missing
            if col_name == "Name":
                default_width = 350
            elif col_name == "Size":
                default_width = 100
            elif col_name == "Modified":
                default_width = 150
            elif col_name == "Type":
                default_width = 120
            
            # Use configured width, fallback to dynamic default, then to fixed default
            width = self.column_widths.get(col_name, default_width)
            self.tree.column(col_name, width=width, stretch=tk.YES)
        
        # Scrollbars - sv_ttk should style these based on the theme.
        # Explicit style names removed to rely on sv_ttk's global styling.
        v_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)
        
        # Status bar
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, style='TLabel') # Explicitly apply TLabel style
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Progress bar and label (initially hidden)
        self.progress_frame = ttk.Frame(self.root, style='TFrame') # Explicitly apply TFrame style
        # self.progress_frame is packed when needed

        self.progress_bar = ttk.Progressbar(self.progress_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress_label = ttk.Label(self.progress_frame, text="")
        self.download_speed_label = ttk.Label(self.progress_frame, text="") # Initialize speed label
        self.download_eta_label = ttk.Label(self.progress_frame, text="") # Initialize ETA label
    
    def _apply_custom_dark_styles(self):
        """Apply specific dark theme styles to ttk widgets, complementing sv_ttk."""
        assert self.root is not None, "self.root must be initialized"
        
        style = ttk.Style(self.root) # Get style object associated with the root window

        # Define colors (adjust these to match Windows default dark mode if needed)
        dark_bg = "#202020"  # Common dark background
        dark_fg = "#ffffff"  # White text
        tree_bg = "#2b2b2b"  # Slightly lighter dark for treeview background
        tree_fg = "#e0e0e0"  # Light gray text for tree items
        select_bg = "#0078d4" # Windows selection blue (can be adjusted)
        select_fg = "#ffffff"  # White text for selected items
        header_bg = "#3c3c3c" # Darker header background

        # Treeview specific styling
        style.configure("Treeview",
                        background=tree_bg,
                        foreground=tree_fg,
                        fieldbackground=tree_bg, # Background of the items area
                        borderwidth=0,
                        relief='flat') # Use flat relief for a more modern look
        
        style.map("Treeview",
                  background=[('selected', select_bg)],
                  foreground=[('selected', select_fg)])

        style.configure("Treeview.Heading",
                        background=header_bg,
                        foreground=dark_fg,
                        relief='flat', # Flat relief for headers
                        borderwidth=0,
                        padding=(6,6)) # Add some padding to headers
        
        style.map("Treeview.Heading",
                  background=[('active', '#4c4c4c'), ('!active', header_bg)], # Slightly lighter on hover
                  relief=[('active', 'groove'), ('!active', 'flat')]) 

    def _on_close(self):
        """Handle window close event, save config and destroy window."""
        self._save_config()
        if self.root:
            self.root.destroy()

    def _load_config(self):
        """Load window geometry and column widths from config file."""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r') as f:
                    config_data = json.load(f)
                    self.window_geometry = config_data.get("geometry", self.window_geometry)
                    loaded_widths = config_data.get("column_widths", {})
                    # Update self.column_widths with loaded values, keeping defaults for missing keys
                    for key, value in loaded_widths.items():
                        if isinstance(value, int): # Basic validation
                            self.column_widths[key] = value
                    self.logger.info(f"Loaded config from {CONFIG_FILE}")
        except FileNotFoundError:
            self.logger.info(f"Config file {CONFIG_FILE} not found. Using defaults.")
        except json.JSONDecodeError:
            self.logger.warning(f"Error decoding JSON from {CONFIG_FILE}. Using defaults.")
        except Exception as e:
            self.logger.error(f"Error loading config: {e}. Using defaults.")

    def _save_config(self):
        """Save current window geometry and column widths to config file."""
        if not self.root or not self.tree: # Ensure GUI elements exist
            return 
        
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True) # Ensure config directory exists
            
            current_geometry = self.root.geometry()
            
            current_column_widths = {}
            # First column #0
            current_column_widths["#0"] = self.tree.column("#0", "width")
            # Other columns
            columns_tuple = ("Name", "Size", "Modified", "Type") # Match definition in _create_gui
            for col_id in columns_tuple:
                current_column_widths[col_id] = self.tree.column(col_id, "width")

            config_data = {
                "geometry": current_geometry,
                "column_widths": current_column_widths
            }
            
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_data, f, indent=4)
            self.logger.info(f"Saved config to {CONFIG_FILE}")
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")

    def _setup_dark_theme(self):
        """Configure comprehensive dark mode theme for all widgets
        NOTE: This method is now largely superseded by sv_ttk and _apply_custom_dark_styles.
        Keeping it for reference or future minor tweaks if necessary.
        """
        pass # Original theme setup is now handled by sv_ttk and _apply_custom_dark_styles
        # style = ttk.Style()
        # Configure dark theme colors
        # dark_bg = '#2b2b2b'
        # dark_fg = '#ffffff'
        # dark_select_bg = '#404040'
        # dark_select_fg = '#ffffff'
        # button_bg = '#404040'
        # button_hover = '#505050'
        # input_bg = '#3c3c3c'
        
        # Set the TTK theme to a base that supports customization
        # available_themes = style.theme_names()
        # if 'clam' in available_themes:
        #     style.theme_use('clam')
        # elif 'alt' in available_themes:
        #     style.theme_use('alt')
        
        # Configure all TTK widget styles
        
        # Frame styles
        # style.configure('Dark.TFrame', 
        #                background=dark_bg,
        #                borderwidth=0)
        # style.configure('TFrame', 
        #                background=dark_bg,
        #                borderwidth=0)
        
        # Label styles
        # style.configure('Dark.TLabel', 
        #                background=dark_bg, 
        #                foreground=dark_fg,
        #                borderwidth=0)
        # style.configure('TLabel', 
        #                background=dark_bg, 
        #                foreground=dark_fg,
        #                borderwidth=0)
        
        # style.configure('DarkPath.TLabel', 
        #                background=input_bg, 
        #                foreground=dark_fg,
        #                relief='sunken',
        #                borderwidth=1,
        #                padding=(8, 4))
        
        # Button styles
        # style.configure('Dark.TButton',
        #                background=button_bg,
        #                foreground=dark_fg,
        #                borderwidth=1,
        #                focuscolor='none',
        #                padding=(8, 4),
        #                relief='raised')
        # style.configure('TButton',
        #                background=button_bg,
        #                foreground=dark_fg,
        #                borderwidth=1,
        #                focuscolor='none',
        #                padding=(8, 4),
        #                relief='raised')
        
        # style.map('Dark.TButton',
        #          background=[('active', button_hover),
        #                     ('pressed', dark_select_bg)])
        # style.map('TButton',
        #          background=[('active', button_hover),
        #                     ('pressed', dark_select_bg)])
        
        # Treeview styles
        # for s_name in ['Dark.Treeview', 'Treeview']:
        #     style.configure(s_name,
        #                    background=input_bg,
        #                    foreground=dark_fg,
        #                    fieldbackground=input_bg,  # Key for item row background
        #                    borderwidth=1,
        #                    relief='solid')
        #     style.map(s_name,
        #              background=[('selected', dark_select_bg)],
        #              foreground=[('selected', dark_select_fg)])

        # for s_name in ['Dark.Treeview.Heading', 'Treeview.Heading']:
        #     style.configure(s_name,
        #                    background=button_bg,
        #                    foreground=dark_fg,
        #                    borderwidth=1,
        #                    relief='raised')
        #     style.map(s_name,
        #              background=[('active', button_hover)])

        # Scrollbar styles
        # for s_prefix in ['Dark.Vertical', 'Vertical']:
        #     style.configure(f'{s_prefix}.TScrollbar',
        #                    background=button_bg,    # Thumb color
        #                    troughcolor=dark_bg,     # Trough color
        #                    borderwidth=1,
        #                    arrowcolor=dark_fg)
        #     style.map(f'{s_prefix}.TScrollbar',
        #              background=[('active', button_hover)])

        # for s_prefix in ['Dark.Horizontal', 'Horizontal']:
        #     style.configure(f'{s_prefix}.TScrollbar',
        #                    background=button_bg,    # Thumb color
        #                    troughcolor=dark_bg,     # Trough color
        #                    borderwidth=1,
        #                    arrowcolor=dark_fg)
        #     style.map(f'{s_prefix}.TScrollbar',
        #              background=[('active', button_hover)])

        # # Progressbar style
        # style.configure('Dark.Horizontal.TProgressbar',
        #                 background=button_bg,  # Color of the progress bar
        #                 troughcolor=dark_bg,   # Color of the trough
        #                 borderwidth=1,
        #                 relief='sunken')
    
    def _update_status(self, message: str): # Added type hint
        """Update the status bar message"""
        assert self.root is not None, "self.root must be initialized for _update_status"
        assert self.status_bar is not None, "self.status_bar must be initialized for _update_status"
        
        self.status_bar.config(text=message)
        self.root.update_idletasks()
    
    def _load_directory(self, path: str): # Added type hint
        """Load directory contents from remote server"""
        assert self.root is not None, "self.root must be initialized for _load_directory"
        assert self.tree is not None, "self.tree must be initialized for _load_directory"
        assert self.path_label is not None, "self.path_label must be initialized for _load_directory"

        self._update_status("Loading directory...")
        
        # Clear current contents
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        try:
            # Construct WebDAV PROPFIND request
            url = urljoin(self.base_url, quote(path.lstrip('/')))
            headers = {
                'Depth': '1',
                'Content-Type': 'application/xml'
            }
            # Basic PROPFIND body
            propfind_body = '''<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:">
    <D:prop>
        <D:displayname/>
        <D:getcontentlength/>
        <D:getlastmodified/>
        <D:resourcetype/>
        <D:getcontenttype/>
    </D:prop>
</D:propfind>'''
            
            response = self.session.request('PROPFIND', url, headers=headers, data=propfind_body, timeout=10)
            
            if response.status_code == 401: # Unauthorized
                self.logger.info(f"Authentication required for {url}")
                self._update_status("Authentication required. Please enter credentials.")
                self._authenticate() # Prompt for credentials
                if self.authenticated:
                    self.logger.info("Retrying request after authentication.")
                    response = self.session.request('PROPFIND', url, headers=headers, data=propfind_body, timeout=10) # Retry the request
                else:
                    self.logger.warning("Authentication failed or was cancelled. Cannot load directory.")
                    self._update_status("Authentication failed. Cannot load directory.")
                    return # Stop if authentication failed

            if response.status_code == 207:  # Multi-Status
                self._parse_webdav_response(response.text, path)
                self.current_path = path
                self.path_label.config(text=path)
                self._update_status(f"Loaded {len(self.tree.get_children())} items")
            else:
                self._update_status(f"Failed to load directory: HTTP {response.status_code}")
                self.logger.error(f"WebDAV PROPFIND failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            self._update_status(f"Error loading directory: {e}")
            self.logger.error(f"Error loading directory {path}: {e}")
    
    def _parse_webdav_response(self, xml_content: str, current_path: str): # Added type hints
        """Parse WebDAV PROPFIND response XML"""
        assert self.tree is not None, "self.tree must be initialized for _parse_webdav_response"
        try:
            root = ET.fromstring(xml_content)
            namespaces = {'D': 'DAV:'}
            
            for response_node in root.findall('.//D:response', namespaces): # Renamed variable
                href_elem = response_node.find('D:href', namespaces)
                if href_elem is None: continue
                href = unquote(href_elem.text or '')
                if href.rstrip('/') == current_path.rstrip('/'): continue
                
                propstat = response_node.find('D:propstat', namespaces)
                if propstat is None: continue
                prop = propstat.find('D:prop', namespaces)
                if prop is None: continue
                
                displayname_elem = prop.find('D:displayname', namespaces)
                name = displayname_elem.text if displayname_elem is not None and displayname_elem.text else os.path.basename(href.rstrip('/'))
                
                size_elem = prop.find('D:getcontentlength', namespaces)
                size = int(size_elem.text) if size_elem is not None and size_elem.text else 0
                
                modified_elem = prop.find('D:getlastmodified', namespaces)
                modified = modified_elem.text if modified_elem is not None and modified_elem.text else ''
                
                resourcetype_elem = prop.find('D:resourcetype', namespaces)
                is_dir = resourcetype_elem is not None and resourcetype_elem.find('D:collection', namespaces) is not None
                
                contenttype_elem = prop.find('D:getcontenttype', namespaces)
                content_type = contenttype_elem.text if contenttype_elem is not None and contenttype_elem.text else ''
                
                icon, file_type_str, size_str = "", "", "" # Initialize
                if is_dir:
                    icon = "📁"
                    file_type_str = "Folder"
                    size_str = ""
                else:
                    ext = os.path.splitext(name)[1].lower()
                    # Simplified icon logic for brevity, can be expanded
                    icon_map = {
                        ('.txt', '.md', '.log'): "📄", ('.jpg', '.jpeg', '.png', '.gif', '.bmp'): "🖼️",
                        ('.mp4', '.avi', '.mkv', '.mov'): "🎬", ('.mp3', '.wav', '.flac', '.ogg'): "🎵",
                        ('.zip', '.rar', '.7z', '.tar', '.gz'): "📦", ('.pdf',): "📕",
                        ('.doc', '.docx'): "📘", ('.xls', '.xlsx'): "📗", ('.ppt', '.pptx'): "📙"
                    }
                    icon = next((v for k, v in icon_map.items() if ext in k), "📄")
                    file_type_str = content_type or mimetypes.guess_type(name)[0] or "File"
                    size_str = self._format_size(size)
                
                self.tree.insert("", "end", 
                    text=icon,
                    values=(name, size_str, modified, file_type_str),
                    tags=("directory" if is_dir else "file",)
                )
        except Exception as e:
            self.logger.error(f"Error parsing WebDAV response: {e}")
            self._update_status("Error parsing server response")
    
    def _format_size(self, size_bytes: int) -> str: # Added type hints
        """Format file size in human readable format"""
        if size_bytes == 0: return "0 B"
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        i = 0
        size_float = float(size_bytes) # Work with float for division
        while size_float >= 1024 and i < len(units) - 1:
            size_float /= 1024
            i += 1
        return f"{size_float:.1f} {units[i]}"
    
    def _on_double_click(self, event: Any): # Added type hint, tk.Event is more specific
        """Handle double-click on tree item"""
        assert self.tree is not None, "self.tree must be initialized for _on_double_click"
        selection = self.tree.selection()
        if not selection: return
        
        item = selection[0]
        values = self.tree.item(item, 'values')
        if not values: return # values could be empty tuple
        name = values[0] # Corrected indentation
        tags = self.tree.item(item, 'tags')
        if "directory" in tags:
            # Navigate to directory
            new_path = os.path.join(self.current_path, name).replace('\\\\', '/')
            if not new_path.startswith('/'): new_path = '/' + new_path
            self.path_history.append(self.current_path)
            self._load_directory(new_path)
        else:
            # Download file
            self._download_selected()
    
    def _on_right_click(self, event: Any): # Added type hint
        """Handle right-click context menu"""
        assert self.tree is not None, "self.tree must be initialized for _on_right_click"
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item) # Ensure item is selected before download
            self._download_selected() # Changed to _download_selected for consistency
    
    def _go_back(self):
        """Go back to previous directory"""
        if len(self.path_history) > 1: # Ensure there's a path to go back to
            previous_path = self.path_history.pop()
            self._load_directory(previous_path)
    
    def _go_home(self):
        """Go to root directory"""
        self.path_history = ["/"] # Reset history correctly
        self._load_directory("/")
    
    def _refresh(self):
        """Refresh current directory"""
        self._load_directory(self.current_path)
    
    def _download_selected(self, event: Optional[tk.Event] = None): # Added event parameter
        """Download selected file or folder"""
        assert self.root is not None, "self.root must be initialized for _download_selected"
        assert self.tree is not None, "self.tree must be initialized for _download_selected"

        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showinfo("Download", "No item selected.", parent=self.root)
            return

        target_base_path_str: Optional[str] = None
        first_item_id = selected_items[0]
        item_data_first = self.tree.item(first_item_id)
        item_type_first = item_data_first['values'][3] # Type is the fourth value
        is_single_folder_download = len(selected_items) == 1 and "Folder" in item_type_first

        if is_single_folder_download:
            target_base_path_str = filedialog.askdirectory(
                title="Select Download Location for Folder",
                initialdir=str(self._default_downloads_path),
                parent=self.root
            )
        elif len(selected_items) > 1 : # Multiple items (files or folders)
             target_base_path_str = filedialog.askdirectory(
                title="Select Download Location for Multiple Items",
                initialdir=str(self._default_downloads_path),
                parent=self.root
            )
        else: # Single file download
            item_name_single_file = item_data_first['values'][0]
            suggested_filename = item_name_single_file
            target_base_path_str = filedialog.asksaveasfilename(
                title="Save File As",
                initialdir=str(self._default_downloads_path),
                initialfile=suggested_filename,
                parent=self.root
            )
            # For a single file, target_base_path_str is the full file path.

        if not target_base_path_str: # User cancelled
            self._update_status("Download cancelled by user.")
            return

        # Show progress bar area
        if self.progress_frame and self.progress_bar and self.progress_label and self.download_speed_label and self.download_eta_label:
            self.progress_label.config(text="Starting download...")
            self.download_speed_label.config(text="Speed: N/A")
            self.download_eta_label.config(text="ETA: N/A")
            self.progress_bar['value'] = 0
            
            # Ensure all progress elements are packed correctly
            self.progress_bar.pack_forget()
            self.progress_label.pack_forget()
            self.download_speed_label.pack_forget()
            self.download_eta_label.pack_forget()

            self.progress_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)
            self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=2)
            self.progress_label.pack(side=tk.LEFT, padx=5, pady=2)
            self.download_speed_label.pack(side=tk.LEFT, padx=5, pady=2)
            self.download_eta_label.pack(side=tk.LEFT, padx=5, pady=2)
        
        download_items_info = [] # List of (remote_path, local_target_path, item_name, is_dir)
        
        for item_id in selected_items:
            item_data = self.tree.item(item_id)
            item_name = item_data['values'][0]
            item_type = item_data['values'][3] 
            is_dir = "Folder" in item_type
            
            remote_item_path_str = str(Path(self.current_path.lstrip('/')) / item_name)
            
            if is_single_folder_download and item_id == first_item_id: # Single folder download, target_base_path_str is the parent directory
                local_item_target_path = Path(target_base_path_str) / item_name # Create the folder inside the selected dir
                download_items_info.append((remote_item_path_str, str(local_item_target_path), item_name, True))
            elif not is_dir and len(selected_items) == 1 and item_id == first_item_id: # Single file download, target_base_path_str is the full file path
                download_items_info.append((remote_item_path_str, target_base_path_str, item_name, False))
            else: # Multiple items, or a folder within a multiple selection. target_base_path_str is the parent directory.
                local_item_target_path = Path(target_base_path_str) / item_name
                download_items_info.append((remote_item_path_str, str(local_item_target_path), item_name, is_dir))

        threading.Thread(target=self._perform_downloads_threaded, args=(download_items_info,), daemon=True).start()

    def _show_message(self, type: str, title: str, message: str):
        """Helper function to show messagebox, ensuring it runs in the main thread."""
        if not self.root:
            self.logger.error("Root window not available for messagebox.")
            return
        
        def _display():
            if type == "info":
                messagebox.showinfo(title, message, parent=self.root)
            elif type == "error":
                messagebox.showerror(title, message, parent=self.root)
            elif type == "warning":
                messagebox.showwarning(title, message, parent=self.root)
        
        if self.root.winfo_exists(): # Check if root window exists before calling after
            self.root.after(0, _display)

    def _perform_downloads_threaded(self, items_to_download: List[Tuple[str, str, str, bool]]):
        """Handles the download of multiple files/folders in a thread."""
        total_items = len(items_to_download)
        downloaded_count = 0

        for remote_path_str, local_target_path_str, item_name, is_dir in items_to_download:
            downloaded_count += 1
            if self.progress_label and self.root and self.root.winfo_exists():
                self.root.after(0, self.progress_label.config, {"text":f"Processing item {downloaded_count}/{total_items}: {item_name}..."})
            
            try:
                if is_dir:
                    self._download_folder_recursive(remote_path_str, Path(local_target_path_str))
                else:
                    self._download_file(remote_path_str, Path(local_target_path_str), item_name)
            except requests.exceptions.HTTPError as e:
                self.logger.error(f"HTTP error downloading {item_name}: {e}")
                self._show_message("error", "Download Error", f"Failed to download {item_name}:\\n{e.response.status_code} {e.response.reason}")
            except Exception as e:
                self.logger.error(f"Unexpected error downloading {item_name}: {e}")
                self._show_message("error", "Download Error", f"Unexpected error for {item_name}:\\n{e}")
        
        if self.progress_label and self.root and self.root.winfo_exists():
             self.root.after(0, self.progress_label.config, {"text":"All downloads completed."})
        if self.progress_bar and self.root and self.root.winfo_exists():
             self.root.after(0, self.progress_bar.config, {"value":100})
        
        self._show_message("info", "Download Complete", f"Finished downloading {total_items} item(s).")

    def _download_file(self, remote_path_str: str, local_file_path: Path, item_name: str): 
        """Download a single file with progress updates."""
        if not self.root: 
            self.logger.error("Root window not available for download updates.")
            return

        # Ensure progress bar elements are available
        if not (self.progress_bar and self.progress_label and self.download_speed_label and self.download_eta_label):
            self.logger.error("Progress bar UI elements not initialized for file download.")
            self.root.after(0, self._update_status, f"Error: Progress UI not ready for {item_name}")
            return

        url = urljoin(self.base_url, quote(remote_path_str.lstrip('/')))
        self.root.after(0, self._update_status, f"Downloading {item_name} to {local_file_path}...")
        self.logger.info(f"Downloading {url} to {local_file_path}")

        try:
            local_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Use self.session for the request
            response = self.session.get(url, stream=True, timeout=60) 
            response.raise_for_status() 
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            start_time = time.time()
            
            if self.progress_label and self.root:
                self.root.after(0, self.progress_label.config, {"text":f"Downloading: {item_name} (0%)"})

            with open(local_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024): # 32KB chunks
                    if chunk: 
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            
                            elapsed_time = time.time() - start_time
                            if elapsed_time > 0.1: # Avoid division by zero or too frequent updates
                                speed = downloaded_size / elapsed_time 
                                eta = (total_size - downloaded_size) / speed if speed > 0 else float('inf')
                                
                                speed_str = f"{speed / 1024:.2f} KB/s" if speed < 1024*1024 else f"{speed / (1024*1024):.2f} MB/s"
                                eta_str = f"{eta:.0f}s" if eta != float('inf') and eta < 36000 else "Calculating..."


                                # Schedule UI updates on the main thread
                                if self.root:
                                    self.root.after(0, self.progress_bar.config, {"value": progress})
                                    if self.progress_label:
                                         self.root.after(0, self.progress_label.config, {"text":f"Downloading: {item_name} ({progress:.1f}%)"})
                                    if self.download_speed_label:
                                        self.root.after(0, self.download_speed_label.config, {"text":f"Speed: {speed_str}"})
                                    if self.download_eta_label:
                                        self.root.after(0, self.download_eta_label.config, {"text":f"ETA: {eta_str}"})
                        # self.root.update_idletasks() # Not ideal from a worker thread, use self.root.after

            if self.root:
                self.root.after(0, self._update_status, f"Downloaded {item_name} successfully.")
            self.logger.info(f"Successfully downloaded {item_name} to {local_file_path}")
            if self.progress_bar and self.root: self.root.after(0, self.progress_bar.config, {"value":100})

        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP error during download of {item_name}: {e.response.status_code} {e.response.reason}")
            self._show_message("error", "Download Error", f"Failed to download {item_name}:\\n{e.response.status_code} {e.response.reason}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error downloading {item_name}: {e}")
            self._show_message("error", "Download Error", f"Network or request error for {item_name}:\\n{e}")
        except Exception as e:
            self.logger.error(f"Unexpected error downloading {item_name}: {e}")
            self._show_message("error", "Download Error", f"Unexpected error for {item_name}:\\n{e}")
        finally:
            # Ensure progress bar is hidden after download completes or fails
            if self.progress_bar and self.root:
                self.root.after(0, self.progress_bar.pack_forget)
            if self.progress_frame and self.root:
                self.root.after(0, self.progress_frame.pack_forget)

    def _download_folder_recursive(self, remote_folder_path_str: str, local_folder_path: Path):
        """Download a folder and its contents recursively."""       
        self.logger.info(f"Downloading folder {remote_folder_path_str} to {local_folder_path}")
        local_folder_path.mkdir(parents=True, exist_ok=True)

        url = urljoin(self.base_url, quote(remote_folder_path_str.lstrip('/')))
        headers = {
            'Depth': '1',
            'Content-Type': 'application/xml'
        }
        propfind_body = '''<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:">
    <D:prop>
        <D:displayname/>
        <D:resourcetype/>
    </D:prop>
</D:propfind>'''

        try:
            # Use self.session for the request
            response = self.session.request('PROPFIND', url, headers=headers, data=propfind_body, timeout=10)
            response.raise_for_status()

            if response.status_code == 401: # Unauthorized
                self.logger.info(f"Authentication required for {url}")
                self._show_message("error", "Authentication Error", f"Authentication required to download folder contents for {remote_folder_path_str}.")
                # We might need to re-authenticate globally here if the session timed out
                # or prompt and retry this specific operation.
                # For now, we log and skip this folder if auth fails during recursive download.
                return

            if response.status_code != 207:
                self.logger.error(f"Failed to list folder {remote_folder_path_str}: HTTP {response.status_code}")
                self._show_message("error", "Download Error", f"Could not list contents of {Path(remote_folder_path_str).name}.")
                return

            root = ET.fromstring(response.content)
            namespaces = {'D': 'DAV:'}
            
            for resp_node in root.findall('.//D:response', namespaces):
                href_elem = resp_node.find('D:href', namespaces)
                if href_elem is None or not href_elem.text:
                    continue
                
                href = unquote(href_elem.text)
                
                item_remote_full_uri_path = href 
                # Strip base_url if present to get path relative to WebDAV service root
                if item_remote_full_uri_path.startswith(self.base_url):
                     item_remote_full_uri_path = item_remote_full_uri_path[len(self.base_url):]
                item_remote_full_uri_path = item_remote_full_uri_path.lstrip('/')


                # Skip the entry for the folder itself
                normalized_href_path = item_remote_full_uri_path.rstrip('/')
                normalized_current_remote_folder_path = remote_folder_path_str.lstrip('/').rstrip('/')
                if normalized_href_path == normalized_current_remote_folder_path:
                    continue

                propstat = resp_node.find('D:propstat', namespaces)
                if propstat is None: continue
                prop = propstat.find('D:prop', namespaces)
                if prop is None: continue

                displayname_elem = prop.find('D:displayname', namespaces)
                # Fallback to last part of href if displayname is missing
                item_name = displayname_elem.text if displayname_elem is not None and displayname_elem.text else Path(normalized_href_path).name
                
                resourcetype_elem = prop.find('D:resourcetype', namespaces)
                is_dir = resourcetype_elem is not None and resourcetype_elem.find('D:collection', namespaces) is not None
                
                local_item_path = local_folder_path / item_name
                
                # item_remote_relative_path is the correct path to pass for recursion or file download
                if is_dir:
                    self._download_folder_recursive(item_remote_relative_path, local_item_path)
                else:
                    self._download_file(item_remote_relative_path, local_item_path, item_name)
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to list/download folder {remote_folder_path_str}: {e}")
            if self.root: 
                self.root.after(0, self._update_status, f"Error with folder {Path(remote_folder_path_str).name}: {e}")
                self.root.after(0, messagebox.showerror, "Download Error", f"Failed to process folder {remote_folder_path_str}:\\n{e}", {"parent": self.root})
        except ET.ParseError as e:
            self.logger.error(f"Failed to parse XML for folder {remote_folder_path_str}: {e}")
            if self.root: self.root.after(0, self._update_status, f"XML error for {Path(remote_folder_path_str).name}")
        except Exception as e: # Catch any other unexpected errors
            self.logger.error(f"Unexpected error downloading folder {remote_folder_path_str}: {e}")
            if self.root: 
                self.root.after(0, self._update_status, f"Unexpected error with {Path(remote_folder_path_str).name}")
                self.root.after(0, messagebox.showerror, "Download Error", f"Unexpected error for folder {Path(remote_folder_path_str).name}:\\n{e}", {"parent": self.root})
    def _open_downloads(self):
        """Open the last used/default downloads folder in the system file explorer"""
        try:
            folder_to_open = self._default_downloads_path
            if not folder_to_open.exists():
                # Fallback if the last saved directory was somehow deleted or is invalid
                folder_to_open = Path.home() / "Downloads"
                folder_to_open.mkdir(parents=True, exist_ok=True)
            
            self.logger.info(f"Opening downloads folder: {folder_to_open}")

            if os.name == 'nt': # Windows
                os.startfile(str(folder_to_open)) # Ensure it's a string for os.startfile
            elif os.name == 'posix': # macOS, Linux
                import subprocess
                if sys.platform == 'darwin': # macOS
                    subprocess.call(['open', str(folder_to_open)])
                else: # Linux and other POSIX
                    subprocess.call(['xdg-open', str(folder_to_open)])
            else:
                messagebox.showinfo("Info", f"Downloads folder: {str(folder_to_open)}")
        except Exception as e:
            self.logger.error(f"Could not open downloads folder: {e}")
            messagebox.showerror("Error", f"Could not open downloads folder: {self._default_downloads_path}\n{e}")
    
    def _authenticate(self):
        """Prompt for and store authentication credentials"""
        assert self.root is not None, "self.root must be initialized for _authenticate"

        # Prompt for password using a modal dialog
        password_dialog = PasswordPromptDialog(self.root, self.peer_name)
        
        if password_dialog.result and password_dialog.username and password_dialog.password:
            self.auth_credentials = (password_dialog.username, password_dialog.password)
            self.session.auth = self.auth_credentials
            self.authenticated = True
            self._update_status("Authenticated")
            self.logger.info("Authentication successful")
            
            # Retry the last operation if applicable
            if self.current_path:
                self._load_directory(self.current_path)
        else:
            self.authenticated = False
            self._update_status("Authentication required")
            self.logger.info("Authentication cancelled by user")

    def _ensure_authenticated(self):
        """Ensure the user is authenticated for operations"""
        assert self.root is not None, "self.root must be initialized for _ensure_authenticated"

        if not self.authenticated:
            self._update_status("Authentication required")
            self.logger.info("Authentication required for this operation")
            
            # Optionally, we could auto-prompt for password here
            # self._authenticate()
            
            # For now, just show an error and return
            messagebox.showerror("Authentication Error", "You must be authenticated to perform this action.", parent=self.root)
            return False
        
        return True

# Example usage (for testing standalone)
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    # This is a dummy URL for testing. Replace with a running WebDAV server.
    # For example, run 'python -m http.server --cgi 8000' in a directory
    # and then use a WebDAV client to connect, or set up a proper WebDAV server.
    # A simple WebDAV server can be started with wsgidav:
    # pip install wsgidav cheroot
    # wsgidav --host=0.0.0.0 --port=8080 --root=.
    
    # Create a dummy WebDAV server for local testing
    from http.server import HTTPServer, SimpleHTTPRequestHandler
    import socket

    class DAVRequestHandler(SimpleHTTPRequestHandler):
        def do_PROPFIND(self):
            # Simplified PROPFIND for testing - returns current directory contents
            # In a real scenario, this needs to be a proper WebDAV response
            self.send_response(207) # Multi-Status
            self.send_header('Content-type', 'application/xml; charset="utf-8"')
            self.end_headers()
            
            current_dir = self.translate_path(self.path)
            
            xml_response = '''<?xml version="1.0" encoding="utf-8"?>
<D:multistatus xmlns:D="DAV:">
    <D:response>
        <D:href>/</D:href>
        <D:propstat><D:prop><D:resourcetype><D:collection/></D:resourcetype></D:prop><D:status>HTTP/1.1 200 OK</D:status></D:propstat>
    </D:response>
'''
            try:
                for item in os.listdir(current_dir):
                    item_path = os.path.join(current_dir, item)
                    item_href = os.path.join(self.path, item).replace('\\\\','/')
                    if not item_href.startswith('/'): item_href = '/' + item_href

                    is_dir = os.path.isdir(item_path)
                    size = os.path.getsize(item_path) if not is_dir else 0
                    modified_time = time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime(os.path.getmtime(item_path)))
                    
                    xml_response += f'''
    <D:response>
        <D:href>{item_href}</D:href>
        <D:propstat>
            <D:prop>
                <D:displayname>{item}</D:displayname>
                <D:getcontentlength>{size}</D:getcontentlength>
                <D:getlastmodified>{modified_time}</D:getlastmodified>
                <D:resourcetype>{ '<D:collection/>' if is_dir else '' }</D:resourcetype>
            </D:prop>
            <D:status>HTTP/1.1 200 OK</D:status>
        </D:propstat>
    </D:response>
'''
            except FileNotFoundError: # Handle cases where path might not be valid during testing
                pass

            xml_response += '</D:multistatus>'
            self.wfile.write(xml_response.encode('utf-8'))

        # Override do_GET to allow downloading files for testing progress bar
        def do_GET(self):
            # Serve a dummy file for download testing
            if "test_large_file.dat" in self.path:
                self.send_response(200)
                self.send_header("Content-type", "application/octet-stream")
                # Simulate a 10MB file
                file_size = 10 * 1024 * 1024 
                self.send_header("Content-Length", str(file_size))
                self.end_headers()
                chunk = b'x' * 8192
                sent_bytes = 0
                while sent_bytes < file_size:
                    self.wfile.write(chunk)
                    sent_bytes += len(chunk)
                    time.sleep(0.01) # Simulate network latency
                return
            super().do_GET()


    PORT = 8088 # Use a different port to avoid conflicts
    # Ensure the server binds to localhost only for security during testing
    server_address = ('localhost', PORT)
    
    # Create a dummy file in the server's root for download testing
    # The server root will be the current directory where this script is run
    if not os.path.exists("dummy_files"):
        os.makedirs("dummy_files")
    with open("dummy_files/test_file1.txt", "w") as f:
        f.write("This is a test file.")
    with open("dummy_files/another_doc.pdf", "w") as f: # Dummy PDF
        f.write("%PDF-1.4 dummy content")
    # Create a dummy large file for progress bar testing
    # This file won't actually be created on disk for the server, it's simulated in do_GET
    # but we can create a placeholder in the listing
    if not os.path.exists("dummy_files/test_large_file.dat"):
         with open("dummy_files/test_large_file.dat", "w") as f:
            f.write("placeholder") # Actual content served by do_GET

    # Change CWD for the server if needed, or ensure files are in the script's dir
    # For this test, let's assume the server serves from a "dummy_files" subdirectory
    os.chdir("dummy_files") # Server will serve from ./dummy_files/
    
    httpd = None
    server_thread = None

    try:
        # Check if port is available
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(server_address) == 0:
                print(f"Port {PORT} is already in use. Please choose another port or stop the existing service.")
            else:
                httpd = HTTPServer(server_address, DAVRequestHandler)
                print(f"Dummy WebDAV server running on http://localhost:{PORT}/ (serving from ./dummy_files relative to script execution)")
                server_thread = threading.Thread(target=httpd.serve_forever)
                server_thread.daemon = True
                server_thread.start()
                
                # The GUI will connect to this server
                # Note: The base_url for FileExplorerGUI should be http://localhost:PORT
                # The paths inside the GUI will be relative to the server\'s root (./dummy_files)
                gui = FileExplorerGUI(peer_name="Test Peer (Local Dummy Server)", base_url=f"http://localhost:{PORT}")
                gui.run()

    except OSError as e:
        print(f"Could not start dummy server (OSError): {e}. Ensure port {PORT} is free.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if httpd:
            print("Shutting down dummy server...")
            httpd.shutdown()
            httpd.server_close()
        if server_thread:
            server_thread.join(timeout=1) # Wait for server thread to finish
        # Change back to original CWD
        os.chdir("..") 
        print("Exited.")
