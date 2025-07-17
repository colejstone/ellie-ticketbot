"""
Helper utility functions for message processing.
"""

import re
from datetime import datetime, timedelta


def sanitize_message(message_text):
    """Remove sensitive information from messages before sending to OpenAI"""
    if not message_text:
        return message_text
        
    # Remove potential sensitive patterns
    sanitized = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[CARD_NUMBER]', message_text)  # Credit cards
    sanitized = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', sanitized)  # SSNs
    sanitized = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', sanitized)  # Emails
    sanitized = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', '[IP_ADDRESS]', sanitized)  # IP addresses
    sanitized = re.sub(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b', '[IP_ADDRESS]', sanitized)  # More IP patterns
    sanitized = re.sub(r'\b[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}\b', '[UUID]', sanitized)  # UUIDs
    sanitized = re.sub(r'\b(?:sk-|pk_|rk_)[A-Za-z0-9_-]+\b', '[API_KEY]', sanitized)  # API keys
    sanitized = re.sub(r'\b[A-Za-z0-9+/]{40,}={0,2}\b', '[TOKEN]', sanitized)  # Long tokens
    sanitized = re.sub(r'\beyJ[A-Za-z0-9+/=._-]+\b', '[TOKEN]', sanitized)  # JWT tokens
    
    return sanitized


def anonymize_username(username, anonymize_usernames=True):
    """Anonymize usernames for OpenAI"""
    if not anonymize_usernames:
        return username
        
    if not username or username == 'Unknown':
        return 'User'
    return f"User_{abs(hash(username)) % 1000}"


def compare_datetime_with_cutoff(timestamp, cutoff):
    """Helper method to compare datetime with cutoff, handling timezone differences"""
    try:
        # If timestamp has timezone info, convert to UTC and make naive
        if hasattr(timestamp, 'replace') and timestamp.tzinfo is not None:
            timestamp_naive = timestamp.replace(tzinfo=None)
        else:
            timestamp_naive = timestamp
        
        # Compare with cutoff (which is already naive UTC)
        return timestamp_naive > cutoff
    except Exception:
        return False 