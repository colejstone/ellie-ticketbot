"""
Rate limiting functionality to prevent abuse.
"""

import time
from collections import defaultdict


class RateLimiter:
    """Rate limiter to prevent abuse"""
    
    def __init__(self, max_requests=5, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
    
    def is_allowed(self, user_id):
        """Check if user is within rate limits"""
        now = time.time()
        user_requests = self.requests[user_id]
        
        # Remove old requests outside the window
        user_requests[:] = [req_time for req_time in user_requests if now - req_time < self.window_seconds]
        
        if len(user_requests) >= self.max_requests:
            return False
        
        user_requests.append(now)
        return True 