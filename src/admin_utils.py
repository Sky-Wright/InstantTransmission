"""
Admin Utilities for InstantTransmission
Handles administrator privileges, firewall rules, and permissions
"""

import os
import sys
import logging
import subprocess
import ctypes
from pathlib import Path

def is_admin():
    """Check if the current process has administrator privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def ensure_admin_privileges():
    """Ensure the application is running with admin privileges"""
    logger = logging.getLogger("AdminUtils")
    
    if is_admin():
        logger.info("Running with administrator privileges")
        return True
    else:
        logger.warning("Administrator privileges required")
        
        # Try to restart with admin privileges
        try:
            # Get the current script path
            script_path = sys.argv[0]
            params = ' '.join(sys.argv[1:])
            
            # Request UAC elevation
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                sys.executable,
                f'"{script_path}" {params}',
                None,
                1  # SW_SHOWNORMAL
            )
            
            if result > 32:  # Success
                logger.info("Restarting with administrator privileges")
                sys.exit(0)  # Exit current process
            else:
                logger.error(f"Failed to elevate privileges: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to request admin privileges: {e}")
            return False

def setup_firewall_rules():
    """Setup Windows Firewall rules for InstantTransmission"""
    logger = logging.getLogger("Firewall")
    
    if not is_admin():
        logger.error("Administrator privileges required for firewall setup")
        return False
    
    try:
        # Get the executable path (for when we build the .exe)
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            exe_path = sys.executable
        else:
            # Running as Python script - use python.exe path
            exe_path = sys.executable
        
        logger.info(f"Setting up firewall rules for: {exe_path}")
          # Define firewall rules - use port-based rules for better compatibility
        rules = [
            {
                'name': 'InstantTransmission-WebDAV-In',
                'description': 'Allow inbound WebDAV connections for InstantTransmission',
                'direction': 'in',
                'protocol': 'TCP',
                'port': '8080',
                'action': 'allow',
                'profile': 'private,domain'  # Only allow on private/domain networks
            },
            {
                'name': 'InstantTransmission-WebDAV-Out',
                'description': 'Allow outbound WebDAV connections for InstantTransmission',
                'direction': 'out',
                'protocol': 'TCP',
                'port': '8080',
                'action': 'allow',
                'profile': 'private,domain'
            },
            {
                'name': 'InstantTransmission-mDNS-In',
                'description': 'Allow inbound mDNS for InstantTransmission',
                'direction': 'in',
                'protocol': 'UDP',
                'port': '5353',
                'action': 'allow',
                'profile': 'private,domain'
            },
            {
                'name': 'InstantTransmission-mDNS-Out',
                'description': 'Allow outbound mDNS for InstantTransmission',
                'direction': 'out',
                'protocol': 'UDP',
                'port': '5353',
                'action': 'allow',
                'profile': 'private,domain'
            }
        ]
        
        for rule in rules:
            success = _add_firewall_rule(rule)
            if success:
                logger.info(f"Added firewall rule: {rule['name']}")
            else:
                logger.warning(f"Failed to add firewall rule: {rule['name']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to setup firewall rules: {e}")
        return False

def _add_firewall_rule(rule):
    """Add a single firewall rule using netsh"""
    logger = logging.getLogger("Firewall")
    
    try:
        # Check if rule already exists
        check_cmd = [
            'netsh', 'advfirewall', 'firewall', 'show', 'rule',
            f'name={rule["name"]}'
        ]
        
        result = subprocess.run(check_cmd, capture_output=True, text=True, shell=True)
        
        if "No rules match" not in result.stdout:
            logger.info(f"Firewall rule {rule['name']} already exists")
            return True
          # Add the rule - build command based on what's available in rule dict
        add_cmd = [
            'netsh', 'advfirewall', 'firewall', 'add', 'rule',
            f'name={rule["name"]}',
            f'description={rule["description"]}',
            f'dir={rule["direction"]}',
            f'action={rule.get("action", "allow")}',
            f'protocol={rule["protocol"]}',
            f'localport={rule["port"]}',
            'enable=yes'
        ]
        
        # Add profile if specified (for private/domain networks only)
        if 'profile' in rule:
            add_cmd.append(f'profile={rule["profile"]}')
        
        # Add program if specified (fallback to old method)
        if 'program' in rule:
            add_cmd.append(f'program={rule["program"]}')
        
        result = subprocess.run(add_cmd, capture_output=True, text=True, shell=True)
        
        if result.returncode == 0:
            return True
        else:
            logger.error(f"netsh error: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error adding firewall rule {rule['name']}: {e}")
        return False

def setup_public_folder_permissions():
    """Setup permissions for the Public folder"""
    logger = logging.getLogger("Permissions")
    
    if not is_admin():
        logger.error("Administrator privileges required for permission setup")
        return False
    
    try:
        # Get Public folder paths to check
        public_paths = [
            Path.home() / "Public",
            Path("C:/Users/Public")
        ]
        
        for public_path in public_paths:
            if public_path.exists():
                logger.info(f"Setting up permissions for: {public_path}")
                
                # Grant Everyone read/write access using icacls
                cmd = [
                    'icacls', str(public_path),
                    '/grant', 'Everyone:(OI)(CI)F',
                    '/T'  # Apply to subfolders and files
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
                
                if result.returncode == 0:
                    logger.info(f"Successfully set permissions for {public_path}")
                else:
                    logger.warning(f"Failed to set permissions for {public_path}: {result.stderr}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to setup Public folder permissions: {e}")
        return False

def remove_firewall_rules():
    """Remove InstantTransmission firewall rules"""
    logger = logging.getLogger("Firewall")
    
    if not is_admin():
        logger.error("Administrator privileges required for firewall cleanup")
        return False
    
    try:
        rule_names = [
            'InstantTransmission-WebDAV-In',
            'InstantTransmission-WebDAV-Out',
            'InstantTransmission-mDNS-In',
            'InstantTransmission-mDNS-Out'
        ]
        
        for rule_name in rule_names:
            cmd = [
                'netsh', 'advfirewall', 'firewall', 'delete', 'rule',
                f'name={rule_name}'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            
            if result.returncode == 0:
                logger.info(f"Removed firewall rule: {rule_name}")
            else:
                logger.warning(f"Failed to remove firewall rule {rule_name}: {result.stderr}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to remove firewall rules: {e}")
        return False

def create_public_folder_if_needed():
    """Create Public folder if it doesn't exist"""
    logger = logging.getLogger("PublicFolder")
    
    try:
        public_folder = Path.home() / "Public"
        
        if not public_folder.exists():
            public_folder.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created Public folder: {public_folder}")
            
            # Create a welcome file
            welcome_file = public_folder / "Welcome to InstantTransmission.txt"
            welcome_file.write_text(
                "Welcome to InstantTransmission!\n\n"
                "This is your Public folder that will be shared with other "
                "InstantTransmission users on your local network.\n\n"
                "You can:\n"
                "- Put files here to share them\n"
                "- Create folders to organize your shared content\n"
                "- Access this folder anytime from the system tray\n\n"
                "Happy sharing!"
            )
            logger.info("Created welcome file in Public folder")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to create Public folder: {e}")
        return False
