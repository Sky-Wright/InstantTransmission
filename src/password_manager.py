"""
Password Manager for InstantTransmission
Handles password configuration and authentication
"""

import json
import logging
import hashlib
import secrets
from pathlib import Path
from typing import Optional, Dict, Any
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

CONFIG_DIR = Path.home() / ".InstantTransmission"
CONFIG_FILE = CONFIG_DIR / "password_config.json"

class PasswordManager:
    """Manages password configuration and authentication for InstantTransmission"""
    
    def __init__(self):
        self.logger = logging.getLogger("PasswordManager")
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self):
        """Load password configuration from file"""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r') as f:
                    self._config = json.load(f)
                self.logger.info("Loaded password configuration")
            else:
                self._config = {"enabled": False, "username": "user", "password_hash": None}
                self._save_config()
        except Exception as e:
            self.logger.error(f"Error loading password config: {e}")
            self._config = {"enabled": False, "username": "user", "password_hash": None}
    
    def _save_config(self):
        """Save password configuration to file"""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self._config, f, indent=2)
            self.logger.info("Saved password configuration")
        except Exception as e:
            self.logger.error(f"Error saving password config: {e}")
    
    def _hash_password(self, password: str) -> str:
        """Create a secure hash of the password"""
        # Use SHA-256 with salt for simple but secure hashing
        salt = secrets.token_hex(32)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}:{password_hash}"
    
    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify a password against stored hash"""
        try:
            salt, hash_value = stored_hash.split(':', 1)
            computed_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return computed_hash == hash_value
        except Exception:
            return False
    
    def is_enabled(self) -> bool:
        """Check if password protection is enabled"""
        return self._config.get("enabled", False)
    
    def get_username(self) -> str:
        """Get the configured username"""
        return self._config.get("username", "user")
    
    def set_password(self, username: str, password: str):
        """Set a new password (enables protection)"""
        self._config["enabled"] = True
        self._config["username"] = username
        self._config["password_hash"] = self._hash_password(password)
        self._save_config()
        self.logger.info("Password protection enabled")
    
    def disable_password(self):
        """Disable password protection"""
        self._config["enabled"] = False
        self._config["password_hash"] = None
        self._save_config()
        self.logger.info("Password protection disabled")
    
    def verify_credentials(self, username: str, password: str) -> bool:
        """Verify provided credentials"""
        if not self.is_enabled():
            return True  # No password protection
        
        stored_hash = self._config.get("password_hash")
        if not stored_hash:
            return True  # No password set
        
        return (username == self.get_username() and 
                self._verify_password(password, stored_hash))
    
    def get_auth_config(self) -> Optional[Dict[str, Any]]:
        """Get authentication configuration for WsgiDAV"""
        if not self.is_enabled():
            return None
        
        return {
            "username": self.get_username(),
            "password_hash": self._config.get("password_hash")
        }
    
    def show_password_dialog(self, parent=None) -> bool:
        """Show password configuration dialog"""
        dialog = PasswordConfigDialog(parent, self)
        return dialog.result

class PasswordConfigDialog:
    """Dialog for configuring password protection"""
    
    def __init__(self, parent, password_manager: PasswordManager):
        self.password_manager = password_manager
        self.result = False
        
        self.dialog = tk.Toplevel(parent) if parent else tk.Tk()
        self.dialog.title("Password Protection Settings")
        self.dialog.geometry("400x300")
        self.dialog.resizable(False, False)
        
        # Center the dialog
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._create_ui()
        
        # Wait for dialog to close
        self.dialog.wait_window()
    
    def _create_ui(self):
        """Create the dialog UI"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Password Protection", 
                               style="Heading.TLabel")
        title_label.pack(pady=(0, 20))
        
        # Enable/Disable checkbox
        self.enabled_var = tk.BooleanVar(value=self.password_manager.is_enabled())
        enabled_check = ttk.Checkbutton(main_frame, 
                                       text="Enable password protection",
                                       variable=self.enabled_var,
                                       command=self._on_enable_changed)
        enabled_check.pack(anchor=tk.W, pady=(0, 20))
        
        # Credentials frame
        self.creds_frame = ttk.LabelFrame(main_frame, text="Credentials", padding="10")
        self.creds_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Username
        ttk.Label(self.creds_frame, text="Username:").pack(anchor=tk.W)
        self.username_var = tk.StringVar(value=self.password_manager.get_username())
        username_entry = ttk.Entry(self.creds_frame, textvariable=self.username_var, width=30)
        username_entry.pack(fill=tk.X, pady=(5, 15))
        
        # Password
        ttk.Label(self.creds_frame, text="Password:").pack(anchor=tk.W)
        self.password_var = tk.StringVar()
        password_entry = ttk.Entry(self.creds_frame, textvariable=self.password_var, 
                                  show="*", width=30)
        password_entry.pack(fill=tk.X, pady=(5, 15))
        
        # Confirm password
        ttk.Label(self.creds_frame, text="Confirm Password:").pack(anchor=tk.W)
        self.confirm_var = tk.StringVar()
        confirm_entry = ttk.Entry(self.creds_frame, textvariable=self.confirm_var, 
                                 show="*", width=30)
        confirm_entry.pack(fill=tk.X, pady=(5, 0))
        
        # Info label
        info_text = ("When enabled, other users will need to enter this username and password "
                    "to access your shared files.")
        info_label = ttk.Label(main_frame, text=info_text, wraplength=360, 
                              style="Info.TLabel")
        info_label.pack(pady=(0, 20))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="Cancel", command=self._cancel).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="OK", command=self._ok).pack(side=tk.RIGHT)
        
        # Update initial state
        self._on_enable_changed()
    
    def _on_enable_changed(self):
        """Handle enable/disable checkbox change"""
        enabled = self.enabled_var.get()
        state = tk.NORMAL if enabled else tk.DISABLED
        
        for widget in self.creds_frame.winfo_children():
            if isinstance(widget, ttk.Entry):
                widget.configure(state=state)
    
    def _ok(self):
        """Handle OK button click"""
        try:
            if self.enabled_var.get():
                # Validate inputs
                username = self.username_var.get().strip()
                password = self.password_var.get()
                confirm = self.confirm_var.get()
                
                if not username:
                    messagebox.showerror("Error", "Username cannot be empty")
                    return
                
                if not password:
                    messagebox.showerror("Error", "Password cannot be empty")
                    return
                
                if password != confirm:
                    messagebox.showerror("Error", "Passwords do not match")
                    return
                
                if len(password) < 4:
                    messagebox.showerror("Error", "Password must be at least 4 characters")
                    return
                
                # Set password
                self.password_manager.set_password(username, password)
                messagebox.showinfo("Success", "Password protection enabled")
            else:
                # Disable protection
                self.password_manager.disable_password()
                messagebox.showinfo("Success", "Password protection disabled")
            
            self.result = True
            self.dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
    
    def _cancel(self):
        """Handle Cancel button click"""
        self.dialog.destroy()

class PasswordPromptDialog:
    """Dialog for prompting user credentials when connecting to protected peer"""
    
    def __init__(self, parent, peer_name: str):
        self.peer_name = peer_name
        self.username = None
        self.password = None
        self.result = False
        
        self.dialog = tk.Toplevel(parent) if parent else tk.Tk()
        self.dialog.title(f"Connect to {peer_name}")
        self.dialog.geometry("350x200")
        self.dialog.resizable(False, False)
        
        # Center the dialog
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._create_ui()
        
        # Wait for dialog to close
        self.dialog.wait_window()
    
    def _create_ui(self):
        """Create the login dialog UI"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_text = f"Authentication Required\n{self.peer_name}"
        title_label = ttk.Label(main_frame, text=title_text, 
                               style="Heading.TLabel", justify=tk.CENTER)
        title_label.pack(pady=(0, 20))
        
        # Username
        ttk.Label(main_frame, text="Username:").pack(anchor=tk.W)
        self.username_var = tk.StringVar(value="user")
        username_entry = ttk.Entry(main_frame, textvariable=self.username_var, width=30)
        username_entry.pack(fill=tk.X, pady=(5, 15))
        
        # Password
        ttk.Label(main_frame, text="Password:").pack(anchor=tk.W)
        self.password_var = tk.StringVar()
        password_entry = ttk.Entry(main_frame, textvariable=self.password_var, 
                                  show="*", width=30)
        password_entry.pack(fill=tk.X, pady=(5, 20))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="Cancel", command=self._cancel).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Connect", command=self._connect).pack(side=tk.RIGHT)
        
        # Focus on username entry
        username_entry.focus()
        
        # Bind Enter key to connect
        self.dialog.bind('<Return>', lambda e: self._connect())
    
    def _connect(self):
        """Handle Connect button click"""
        self.username = self.username_var.get().strip()
        self.password = self.password_var.get()
        
        if not self.username or not self.password:
            messagebox.showerror("Error", "Please enter both username and password")
            return
        
        self.result = True
        self.dialog.destroy()
    
    def _cancel(self):
        """Handle Cancel button click"""
        self.dialog.destroy()

# Test the password manager
if __name__ == "__main__":
    import sys
    import sv_ttk
    
    root = tk.Tk()
    root.withdraw()  # Hide main window
    
    sv_ttk.set_theme("dark")
    
    pm = PasswordManager()
    
    # Test configuration dialog
    pm.show_password_dialog()
    
    print(f"Password enabled: {pm.is_enabled()}")
    if pm.is_enabled():
        print(f"Username: {pm.get_username()}")
    
    root.destroy()
