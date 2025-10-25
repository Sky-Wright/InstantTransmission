"""
Custom Domain Controller for InstantTransmission
Handles authentication with our password manager
"""

import logging
from wsgidav.domain_controller import DomainController
from .password_manager import PasswordManager

class InstantTransmissionDomainController(DomainController):
    """Custom domain controller that integrates with PasswordManager"""
    
    def __init__(self, password_manager: PasswordManager):
        super().__init__()
        self.password_manager = password_manager
        self.logger = logging.getLogger("AuthController")
    
    def get_domain_realm(self, input_url, environ):
        """Return the domain/realm for the request"""
        return "InstantTransmission"
    
    def require_authentication(self, realm, environ):
        """Check if authentication is required"""
        return self.password_manager.is_enabled()
    
    def is_realm_user(self, realm, user_name, environ):
        """Check if user exists in this realm"""
        if not self.password_manager.is_enabled():
            return True
        return user_name == self.password_manager.get_username()
    
    def get_password(self, realm, user_name, environ):
        """Get password for verification - not used with custom auth"""
        return None
    
    def authenticate(self, realm, user_name, password, environ):
        """Authenticate user credentials"""
        if not self.password_manager.is_enabled():
            return True
        
        result = self.password_manager.verify_credentials(user_name, password)
        if result:
            self.logger.info(f"Authentication successful for user: {user_name}")
        else:
            self.logger.warning(f"Authentication failed for user: {user_name}")
        
        return result
