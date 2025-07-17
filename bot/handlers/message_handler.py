"""
Message handling and storage functionality.
"""

import logging
from datetime import datetime, timedelta
from ..utils.helpers import sanitize_message, anonymize_username, compare_datetime_with_cutoff

logger = logging.getLogger(__name__)


class MessageHandler:
    """Handle message storage and retrieval"""
    
    def __init__(self, config, security_logger, persistence_manager=None):
        self.config = config
        self.security_logger = security_logger
        self.persistence_manager = persistence_manager
        self.recent_messages = []
        self.max_context_messages = config.max_context_messages
        self.anonymize_usernames = config.anonymize_usernames
    
    def is_chat_whitelisted(self, chat_id):
        """Check if a chat is whitelisted for bot operations"""
        if not self.config.whitelisted_chats:
            # If no whitelist is configured, only allow the primary chat
            return chat_id == self.config.chat_id
        return chat_id in self.config.whitelisted_chats
    
    def store_message(self, message):
        """Store message temporarily in memory with security checks and persistence"""
        if not message.text or len(message.text) < 10:
            return
            
        # Security check: ensure message is from whitelisted chat
        if not self.is_chat_whitelisted(message.chat_id):
            self.security_logger.log_event("UNAUTHORIZED_MESSAGE", f"Message from non-whitelisted chat: {message.chat_id}")
            return
        
        # Check if message was already processed (if persistence is available)
        if self.persistence_manager and self.persistence_manager.is_message_processed(message.id, message.chat_id):
            logger.debug(f"Message {message.id} already processed, skipping storage")
            return
            
        msg_data = {
            'id': message.id,
            'text': sanitize_message(message.text),
            'username': anonymize_username(message.sender.username if message.sender else 'Unknown', self.anonymize_usernames),
            'timestamp': message.date,
            'user_id': message.sender_id,
            'chat_id': message.chat_id
        }
        
        self.recent_messages.append(msg_data)
        logger.debug(f"Stored message from @{msg_data['username']}: {msg_data['text'][:50]}...")
        
        # Mark message as processed in persistent storage
        if self.persistence_manager:
            self.persistence_manager.mark_message_processed(
                message.id, 
                message.chat_id, 
                message.sender_id, 
                message.date
            )
        
        # Keep only last 24 hours of messages
        cutoff = datetime.utcnow() - timedelta(hours=24)
        old_count = len(self.recent_messages)
        self.recent_messages = [
            msg for msg in self.recent_messages 
            if compare_datetime_with_cutoff(msg['timestamp'], cutoff)
        ]
        
        if len(self.recent_messages) < old_count:
            logger.info(f"Cleaned up {old_count - len(self.recent_messages)} old messages")
    
    def get_context_messages(self):
        """Get recent context messages (limited for security)"""
        return sorted(self.recent_messages, key=lambda x: x['timestamp'])[-self.max_context_messages:]
    
    def find_message_by_id(self, message_id):
        """Find a message by ID in recent messages"""
        for msg in self.recent_messages:
            if msg['id'] == message_id:
                return msg
        return None
    
    async def fetch_message_from_telegram(self, client, chat_id, message_id):
        """Fetch a message directly from Telegram if not in recent storage"""
        try:
            logger.info(f"Trigger message not in recent storage, fetching from Telegram...")
            message = await client.get_messages(chat_id, ids=message_id)
            if message:
                trigger_msg = {
                    'id': message.id,
                    'text': sanitize_message(message.text or ''),
                    'username': anonymize_username(message.sender.username if message.sender else 'Unknown', self.anonymize_usernames),
                    'timestamp': message.date,
                    'user_id': message.sender_id,
                    'chat_id': message.chat_id
                }
                logger.info(f"Successfully fetched trigger message: {trigger_msg['text'][:50]}...")
                return trigger_msg
            else:
                logger.warning(f"Could not fetch message {message_id} from Telegram")
                return None
        except Exception as e:
            logger.error(f"Error fetching message {message_id}: {e}")
            return None 