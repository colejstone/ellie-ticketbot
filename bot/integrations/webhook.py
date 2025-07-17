"""
Webhook integration for sending issues to external services.
"""

import json
import hmac
import hashlib
import logging
from datetime import datetime
import aiohttp

logger = logging.getLogger(__name__)


class WebhookClient:
    """Webhook client for secure external integrations"""
    
    def __init__(self, webhook_url, webhook_secret, security_logger):
        self.webhook_url = webhook_url
        self.webhook_secret = webhook_secret
        self.security_logger = security_logger
    
    def generate_webhook_signature(self, payload):
        """Generate HMAC signature for webhook security"""
        return hmac.new(
            self.webhook_secret.encode('utf-8'),
            json.dumps(payload, sort_keys=True).encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def send_context_to_n8n(self, trigger_message, context_messages, user_id):
        """Send raw message context to n8n webhook for processing"""
        if not self.webhook_url:
            logger.info("No webhook configured - would have sent context:")
            logger.info(f"Trigger: {trigger_message['text'][:100]}...")
            logger.info(f"Context: {len(context_messages)} messages")
            return True
        
        if not self.webhook_secret:
            logger.error("WEBHOOK_SECRET not configured")
            self.security_logger.log_event("WEBHOOK_NO_SECRET", "Webhook request attempted without secret")
            return False
        
        # Prepare payload with raw context for n8n processing
        payload = {
            "source": "telegram",
            "type": "issue_analysis_request",
            "chat_id": trigger_message['chat_id'],
            "trigger_user": trigger_message['username'],
            "trigger_user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "trigger_message": {
                "id": trigger_message['id'],
                "text": trigger_message['text'],
                "username": trigger_message['username'],
                "timestamp": trigger_message['timestamp'].isoformat() if hasattr(trigger_message['timestamp'], 'isoformat') else str(trigger_message['timestamp']),
                "user_id": trigger_message['user_id'],
                "chat_id": trigger_message['chat_id']
            },
            "context_messages": [
                {
                    "id": msg['id'],
                    "text": msg['text'],
                    "username": msg['username'],
                    "timestamp": msg['timestamp'].isoformat() if hasattr(msg['timestamp'], 'isoformat') else str(msg['timestamp']),
                    "user_id": msg['user_id'],
                    "chat_id": msg['chat_id']
                }
                for msg in context_messages
            ],
            "security_version": "1.0"
        }
        
        signature = self.generate_webhook_signature(payload)
        headers = {
            'X-Webhook-Signature': f'sha256={signature}',
            'Content-Type': 'application/json',
            'User-Agent': 'EllieTicketBot/1.0'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url, 
                    json=payload, 
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),  # Increased timeout for processing
                    ssl=True  # Ensure SSL verification
                ) as resp:
                    if resp.status == 200:
                        logger.info(f"Context sent to n8n webhook successfully")
                        self.security_logger.log_event("WEBHOOK_SUCCESS", "Context sent to n8n webhook")
                        return True
                    else:
                        logger.error(f"n8n webhook failed with status: {resp.status}")
                        self.security_logger.log_event("WEBHOOK_ERROR", f"Status: {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"n8n webhook request failed: {e}")
            self.security_logger.log_event("WEBHOOK_EXCEPTION", str(e))
            return False

    # Keep the old method for backward compatibility, but mark as deprecated
    async def send_issue(self, issue_data, trigger_message, user_id):
        """DEPRECATED: Use send_context_to_n8n instead"""
        logger.warning("send_issue method is deprecated, please use send_context_to_n8n")
        return await self.send_context_to_n8n(trigger_message, [], user_id) 