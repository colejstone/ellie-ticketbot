"""
Security event logging functionality.
"""

import os
import logging
import logging.handlers


class SecurityLogger:
    """Security event logger"""
    
    def __init__(self):
        self.security_logger = logging.getLogger('security')
        self.security_logger.setLevel(logging.WARNING)
        
        # Create security log handler
        security_handler = logging.handlers.RotatingFileHandler(
            'security.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        security_handler.setFormatter(logging.Formatter(
            '%(asctime)s - SECURITY - %(levelname)s - %(message)s'
        ))
        self.security_logger.addHandler(security_handler)
        
        # Set secure permissions on log file
        if os.path.exists('security.log'):
            os.chmod('security.log', 0o600)
    
    def log_event(self, event_type, details, user_id=None):
        """Log security events"""
        message = f"EVENT: {event_type} | DETAILS: {details}"
        if user_id:
            message += f" | USER: {user_id}"
        self.security_logger.warning(message) 