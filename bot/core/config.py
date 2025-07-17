"""
Configuration handling and validation for the bot.
"""

import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class BotConfig:
    """Bot configuration management"""
    
    def __init__(self):
        self.validate_environment()
        self.load_config()
    
    def validate_environment(self):
        """Validate required environment variables"""
        required_vars = {
            'TELEGRAM_API_ID': 'Telegram API ID from https://my.telegram.org',
            'TELEGRAM_API_HASH': 'Telegram API Hash from https://my.telegram.org',
            'WHITELISTED_CHATS': 'Comma-separated list of chat IDs for security',
            'WHITELISTED_USERS': 'Comma-separated list of user IDs who can trigger reactions',
            'N8N_WEBHOOK_URL': 'N8N webhook URL for processing messages',
            'WEBHOOK_SECRET': 'Secret key for webhook authentication'
        }
        
        optional_vars = {
            'OPENAI_API_KEY': 'OpenAI API key (optional - now handled by n8n)'
        }
        
        missing_vars = []
        for var, description in required_vars.items():
            if not os.getenv(var):
                missing_vars.append(f"  {var}: {description}")
        
        if missing_vars:
            logger.error("❌ Missing required environment variables:")
            for var in missing_vars:
                logger.error(var)
            logger.error("\nPlease create a .env file with these variables.")
            logger.error("See README.md for setup instructions.")
            raise ValueError("Missing required environment variables")
        
        # Log optional variables
        for var, description in optional_vars.items():
            if not os.getenv(var):
                logger.info(f"ℹ️  Optional variable not set: {var} - {description}")
        
        # Validate numeric variables
        try:
            int(os.getenv('TELEGRAM_API_ID'))
        except (ValueError, TypeError):
            raise ValueError("TELEGRAM_API_ID must be a number")
        
        # Validate chat IDs format
        whitelisted_chats = os.getenv('WHITELISTED_CHATS', '')
        if whitelisted_chats:
            try:
                for chat_id in whitelisted_chats.split(','):
                    int(chat_id.strip())
            except (ValueError, TypeError):
                raise ValueError("WHITELISTED_CHATS must be comma-separated numbers")
        
        # Validate user IDs format
        whitelisted_users = os.getenv('WHITELISTED_USERS', '')
        if whitelisted_users:
            try:
                for user_id in whitelisted_users.split(','):
                    int(user_id.strip())
            except (ValueError, TypeError):
                raise ValueError("WHITELISTED_USERS must be comma-separated numbers")
        
        logger.info("✅ All required environment variables are present")
    
    def load_config(self):
        """Load configuration from environment variables"""
        # Core credentials
        self.api_id = os.getenv('TELEGRAM_API_ID')
        self.api_hash = os.getenv('TELEGRAM_API_HASH')
        self.openai_key = os.getenv('OPENAI_API_KEY')  # Optional now
        
        # Chat and user configuration
        self.chat_id = os.getenv('CHAT_ID')
        self.whitelisted_chats = self._parse_whitelist(os.getenv('WHITELISTED_CHATS', ''))
        self.whitelisted_users = self._parse_user_whitelist(os.getenv('WHITELISTED_USERS', ''))
        
        # Webhook configuration (now required)
        self.n8n_webhook = os.getenv('N8N_WEBHOOK_URL')
        self.webhook_secret = os.getenv('WEBHOOK_SECRET')
        
        # Security configuration
        self.anonymize_usernames = os.getenv('ANONYMIZE_USERNAMES', 'true').lower() == 'true'
        self.max_context_messages = int(os.getenv('MAX_CONTEXT_MESSAGES', '25'))
        self.rate_limit_requests = int(os.getenv('RATE_LIMIT_REQUESTS', '5'))
        self.encrypt_sessions = os.getenv('ENCRYPT_SESSION_FILES', 'false').lower() == 'true'
        
        # Convert chat_id to int if provided
        if self.chat_id:
            try:
                self.chat_id = int(self.chat_id)
                # Add primary chat to whitelist automatically
                if self.chat_id not in self.whitelisted_chats:
                    self.whitelisted_chats.add(self.chat_id)
            except ValueError:
                logger.error(f"Invalid CHAT_ID format: {self.chat_id}")
                self.chat_id = None
        
        # Validate webhook security
        if self.n8n_webhook and not self.webhook_secret:
            raise ValueError("WEBHOOK_SECRET is required when N8N_WEBHOOK_URL is configured")
    
    def _parse_whitelist(self, whitelist_str):
        """Parse comma-separated chat IDs into a set"""
        if not whitelist_str:
            return set()
        
        chat_ids = set()
        for chat_id in whitelist_str.split(','):
            try:
                chat_ids.add(int(chat_id.strip()))
            except ValueError:
                logger.warning(f"Invalid chat ID in whitelist: {chat_id}")
        return chat_ids
    
    def _parse_user_whitelist(self, whitelist_str):
        """Parse comma-separated user IDs into a set"""
        if not whitelist_str:
            return set()
        
        user_ids = set()
        for user_id in whitelist_str.split(','):
            try:
                user_ids.add(int(user_id.strip()))
            except ValueError:
                logger.warning(f"Invalid user ID in whitelist: {user_id}")
        return user_ids 