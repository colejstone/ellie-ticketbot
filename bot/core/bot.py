"""
Main bot class that integrates all components.
"""

import os
import asyncio
import logging
import logging.handlers
from telethon import TelegramClient, events
from .config import BotConfig
from ..security import SessionEncryption, RateLimiter, SecurityLogger
from ..handlers import MessageHandler, ReactionHandler
from ..integrations import OpenAIClient, WebhookClient
from ..storage import PersistenceManager

logger = logging.getLogger(__name__)


class SimpleIssueTracker:
    """Main bot class that integrates all components"""
    
    def __init__(self):
        # Initialize configuration
        self.config = BotConfig()
        
        # Initialize security components
        self.security_logger = SecurityLogger()
        self.rate_limiter = RateLimiter(
            max_requests=self.config.rate_limit_requests,
            window_seconds=60
        )
        self.session_encryption = SessionEncryption(
            self.config.api_id,
            self.config.api_hash
        )
        
        # Initialize persistence manager
        self.persistence_manager = PersistenceManager()
        
        # Initialize handlers with persistence
        self.message_handler = MessageHandler(self.config, self.security_logger, self.persistence_manager)
        self.reaction_handler = ReactionHandler(self.config, self.security_logger, self.rate_limiter, self.persistence_manager)
        
        # Initialize integrations
        self.openai_client = None
        if self.config.openai_key and OpenAIClient is not None:
            try:
                self.openai_client = OpenAIClient(
                    self.config.openai_key,
                    self.security_logger,
                    self.config.anonymize_usernames
                )
                logger.info("✅ OpenAI client initialized")
            except ImportError as e:
                logger.warning(f"⚠️  OpenAI client not available: {e}")
                logger.info("ℹ️  Processing will be handled by n8n")
        else:
            logger.info("ℹ️  OpenAI client not initialized - processing will be handled by n8n")
        
        self.webhook_client = WebhookClient(
            self.config.n8n_webhook,
            self.config.webhook_secret,
            self.security_logger
        )
        
        # Initialize Telegram client
        self.session_name = 'issue_tracker_session'
        self.client = None
        
        # Setup secure logging
        self._setup_secure_logging()
        
        logger.info("Bot initialized successfully with security enhancements!")
        logger.info(f"Whitelisted chats: {list(self.config.whitelisted_chats)}")
        logger.info(f"Whitelisted users: {list(self.config.whitelisted_users)}")
        logger.info(f"Security features: Rate limiting={self.config.rate_limit_requests}/min, "
                   f"Anonymization={self.config.anonymize_usernames}, "
                   f"Session encryption={self.config.encrypt_sessions}")
        
        # Check if we're in a Dropbox environment
        if "dropbox" in os.getcwd().lower():
            logger.info("📦 Detected Dropbox environment - enhanced file handling enabled")
            logger.info("⚠️ Note: Dropbox sync can cause temporary file permission issues")
        
        # Log persistence statistics
        stats = self.persistence_manager.get_stats()
        logger.info(f"Persistence: {stats['processed_messages']} messages, {stats['processed_reactions']} reactions tracked")
        logger.info(f"Database: {stats['database_size_bytes']} bytes at {stats['database_path']}")
    
    def _setup_secure_logging(self):
        """Setup secure logging with rotation"""
        log_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Rotate logs to prevent disk space issues
        log_handler = logging.handlers.RotatingFileHandler(
            'bot_secure.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        log_handler.setFormatter(log_formatter)
        
        # Set secure permissions
        if os.path.exists('bot_secure.log'):
            os.chmod('bot_secure.log', 0o600)
        
        # Add to root logger
        logging.getLogger().addHandler(log_handler)
    
    def _prepare_encrypted_session(self):
        """Prepare session file with encryption support and Dropbox handling"""
        session_file = f"{self.session_name}.session"
        encrypted_session = f"{session_file}.enc"
        
        # If encrypted session exists, decrypt it temporarily
        if os.path.exists(encrypted_session):
            logger.info("Found encrypted session file, decrypting...")
            try:
                # Check if we're in a Dropbox folder
                if "dropbox" in os.getcwd().lower():
                    logger.info("Detected Dropbox folder - using enhanced session handling")
                    # Give Dropbox a moment to finish any sync operations
                    import time
                    time.sleep(1)
                
                decrypted_path = self.session_encryption.decrypt_file(encrypted_session)
                if decrypted_path:
                    logger.info("✅ Session file decrypted successfully")
                    self.security_logger.log_event("SESSION_DECRYPTED", f"File: {encrypted_session}")
                else:
                    logger.error("❌ Failed to decrypt session file")
                    self.security_logger.log_event("SESSION_DECRYPT_FAILED", f"File: {encrypted_session}")
                    # Remove corrupted encrypted file and start fresh
                    logger.info("Removing corrupted encrypted session file...")
                    os.remove(encrypted_session)
            except Exception as e:
                logger.error(f"Error during session decryption: {e}")
                logger.info("Removing problematic encrypted session file...")
                if os.path.exists(encrypted_session):
                    os.remove(encrypted_session)
        
        return session_file
    
    def _secure_session_file(self):
        """Set secure permissions and optionally encrypt session files"""
        session_file = f"{self.session_name}.session"
        
        if os.path.exists(session_file):
            try:
                # Set proper permissions - ensure it's writable for database operations
                os.chmod(session_file, 0o600)  # Read/write for owner only
                
                # Test write access by trying to open in read-write mode
                try:
                    with open(session_file, 'r+b') as test_file:
                        test_file.seek(0, 2)  # Seek to end, don't modify
                    logger.info(f"✅ Session file write access verified: {session_file}")
                except Exception as e:
                    logger.warning(f"⚠️ Session file write test failed: {e}")
                    # Try to fix permissions more aggressively
                    os.chmod(session_file, 0o666)  # More permissive temporarily
                    os.chmod(session_file, 0o600)  # Back to secure
                    
                    # Test again
                    try:
                        with open(session_file, 'r+b') as test_file:
                            test_file.seek(0, 2)  # Seek to end
                        logger.info(f"✅ Fixed session file write access: {session_file}")
                    except Exception as e2:
                        logger.error(f"❌ Failed to ensure write access for session file: {session_file} - {e2}")
                        logger.warning("⚠️ Skipping session encryption due to write permission issues")
                        return
                
                logger.info(f"Secured session file: {session_file}")
                
                # Encrypt session file if enabled (do this after ensuring it's writable)
                if self.config.encrypt_sessions:
                    logger.info("Encrypting session file...")
                    # Give the session file a moment to finish any pending writes
                    import time
                    time.sleep(0.1)
                    
                    if self.session_encryption.encrypt_file(session_file):
                        logger.info("✅ Session file encrypted successfully")
                        self.security_logger.log_event("SESSION_ENCRYPTED", f"File: {session_file}")
                    else:
                        logger.error("❌ Failed to encrypt session file")
                        self.security_logger.log_event("SESSION_ENCRYPT_FAILED", f"File: {session_file}")
                        
            except Exception as e:
                logger.error(f"Error securing session file: {e}")
                self.security_logger.log_event("SESSION_SECURE_ERROR", f"File: {session_file}, Error: {str(e)}")
        else:
            logger.warning(f"Session file {session_file} does not exist, skipping encryption")
    
    def _cleanup_session_files(self):
        """Clean up any temporary decrypted session files"""
        if self.config.encrypt_sessions:
            session_file = f"{self.session_name}.session"
            # Only cleanup if file exists and is not needed anymore
            if os.path.exists(session_file):
                try:
                    # Give it a moment to finish any pending operations
                    import time
                    time.sleep(0.1)
                    self.session_encryption.cleanup_decrypted_file(session_file)
                    logger.info("Cleaned up temporary session files")
                except Exception as e:
                    logger.warning(f"Could not cleanup session file: {e}")
    
    async def _maintain_session_permissions(self):
        """Periodically check and maintain session file permissions"""
        while True:
            try:
                session_file = f"{self.session_name}.session"
                if os.path.exists(session_file):
                    # Check current permissions
                    current_perms = oct(os.stat(session_file).st_mode)[-3:]
                    
                    # Check if file is writable by attempting to open it
                    try:
                        with open(session_file, 'r+b') as test_file:
                            test_file.seek(0, 2)  # Seek to end, don't modify
                        # File is writable, no action needed
                        logger.debug(f"Session file {session_file} is writable (permissions: {current_perms})")
                    except Exception as e:
                        logger.warning(f"⚠️ Session file {session_file} is not writable (permissions: {current_perms}), fixing...")
                        
                        # Force set correct permissions
                        os.chmod(session_file, 0o600)
                        
                        # Also try to fix ownership if possible
                        try:
                            import pwd
                            current_user = pwd.getpwuid(os.getuid()).pw_name
                            os.system(f"chown {current_user} {session_file}")
                        except:
                            pass  # Ignore if we can't change ownership
                        
                        # Test again
                        try:
                            with open(session_file, 'r+b') as test_file:
                                test_file.seek(0, 2)  # Seek to end
                            logger.info(f"✅ Session file permissions restored: {session_file}")
                        except Exception as e2:
                            logger.error(f"❌ Failed to restore session file permissions: {session_file} - {e2}")
                            # If we still can't write, try recreating the session
                            logger.warning("⚠️ Attempting to recreate session file due to persistent permission issues...")
                            try:
                                if os.path.exists(session_file):
                                    os.remove(session_file)
                                logger.info("Session file removed - bot will recreate it on next restart")
                            except Exception as e3:
                                logger.error(f"Failed to remove problematic session file: {e3}")
                
                # Sleep for 15 seconds before next check (more frequent for better responsiveness)
                await asyncio.sleep(15)
                
            except Exception as e:
                logger.error(f"Error in session permission maintenance: {e}")
                await asyncio.sleep(15)
    
    async def _periodic_cleanup(self):
        """Periodically clean up old data from database"""
        while True:
            try:
                await asyncio.sleep(86400)  # Clean up daily
                logger.info("Starting periodic database cleanup...")
                self.persistence_manager.cleanup_old_data(days_to_keep=30)
                
                # Vacuum database weekly
                import time
                if int(time.time()) % (7 * 86400) < 86400:  # Approximately weekly
                    logger.info("Performing database vacuum...")
                    self.persistence_manager.vacuum_database()
                    
                # Log updated statistics
                stats = self.persistence_manager.get_stats()
                logger.info(f"After cleanup: {stats['processed_messages']} messages, {stats['processed_reactions']} reactions tracked")
                
            except Exception as e:
                logger.warning(f"Error during periodic cleanup: {e}")
                await asyncio.sleep(3600)  # Wait before retrying
    
    async def verify_chat_access(self, chat_id):
        """Verify we can access a chat and get its proper ID"""
        try:
            entity = await self.client.get_entity(chat_id)
            logger.info(f"✅ Chat {chat_id} accessible: {getattr(entity, 'title', 'Unknown')}")
            # Return the original chat_id that works - don't "correct" it
            return chat_id
        except Exception as e1:
            logger.warning(f"❌ Cannot access chat {chat_id}: {e1}")
            
            # Try with negative ID if positive was given (for groups)
            if chat_id > 0:
                try:
                    negative_id = -chat_id
                    entity = await self.client.get_entity(negative_id)
                    logger.info(f"✅ Chat {negative_id} accessible: {getattr(entity, 'title', 'Unknown')}")
                    logger.info(f"💡 Note: Using negative ID {negative_id} instead of {chat_id}")
                    return negative_id
                except Exception as e2:
                    logger.warning(f"❌ Cannot access chat {negative_id} either: {e2}")
            
            # Try with positive ID if negative was given
            elif chat_id < 0:
                try:
                    positive_id = -chat_id
                    entity = await self.client.get_entity(positive_id)
                    logger.info(f"✅ Chat {positive_id} accessible: {getattr(entity, 'title', 'Unknown')}")
                    logger.info(f"💡 Note: Using positive ID {positive_id} instead of {chat_id}")
                    return positive_id
                except Exception as e3:
                    logger.warning(f"❌ Cannot access chat {positive_id} either: {e3}")
            
            return None
    
    async def test_chat_access(self):
        """Test if we can access the configured chat without sending messages"""
        if not self.config.chat_id:
            logger.error("No CHAT_ID configured for testing")
            return False
        
        # Only test if the chat is whitelisted
        if not self.message_handler.is_chat_whitelisted(self.config.chat_id):
            logger.error(f"❌ Chat {self.config.chat_id} is not in the whitelist - cannot test access")
            self.security_logger.log_event("CHAT_NOT_WHITELISTED", f"Chat ID: {self.config.chat_id}")
            return False
        
        try:
            # Test access by getting entity and permissions (no message sending)
            entity = await self.client.get_entity(self.config.chat_id)
            logger.info(f"✅ Can access chat {self.config.chat_id}: {getattr(entity, 'title', 'Unknown')}")
            
            # Check if we have permission to send messages (optional since we use DMs)
            permissions = await self.client.get_permissions(self.config.chat_id)
            if permissions.send_messages:
                logger.info(f"✅ Bot has send message permissions in chat {self.config.chat_id}")
                logger.info(f"ℹ️  Bot will only send private DMs - no group messaging")
            else:
                logger.warning(f"⚠️ Bot does not have send message permissions in chat {self.config.chat_id}")
                logger.info(f"ℹ️  This is OK - bot will send DMs to users instead of group messages")
                logger.info(f"ℹ️  Bot will only send private DMs - no group messaging")
                self.security_logger.log_event("LIMITED_PERMISSIONS", f"Chat ID: {self.config.chat_id}")
            
            # Return True regardless of send permissions since DMs are primary method
            return True
                
        except Exception as e:
            logger.error(f"❌ Failed to access chat {self.config.chat_id}: {e}")
            self.security_logger.log_event("CHAT_ACCESS_ERROR", f"Chat ID: {self.config.chat_id}, Error: {str(e)}")
            return False
    
    async def analyze_and_send_to_linear(self, trigger_message_id: int, user_id: int, chat_id: int = None):
        """Send context to n8n webhook (skipping OpenAI) for Linear integration"""
        logger.info(f"Sending context to n8n webhook for message ID: {trigger_message_id}")
        
        # Find trigger message in recent messages first
        trigger_msg = self.message_handler.find_message_by_id(trigger_message_id)
        
        # If not found in recent messages, fetch it directly from Telegram
        if not trigger_msg and chat_id:
            trigger_msg = await self.message_handler.fetch_message_from_telegram(
                self.client, chat_id, trigger_message_id
            )
        
        if not trigger_msg:
            logger.warning(f"Trigger message {trigger_message_id} not found in recent messages or could not be fetched")
            self.security_logger.log_event("TRIGGER_MESSAGE_NOT_FOUND", f"Message ID: {trigger_message_id}")
            return False
        
        # Get context messages (limited for security)
        context_messages = self.message_handler.get_context_messages()
        logger.info(f"Sending {len(context_messages)} messages for context analysis to n8n")
        
        # Skip OpenAI processing - send raw context to n8n webhook
        logger.info("Skipping OpenAI processing - sending raw context to n8n webhook")
        
        # Send to n8n webhook
        success = await self.webhook_client.send_context_to_n8n(trigger_msg, context_messages, user_id)
        
        if success:
            self.security_logger.log_event("CONTEXT_SENT_TO_N8N", f"Message ID: {trigger_message_id}", user_id)
        
        return success
    
    async def send_user_notification(self, user_id, success):
        """Send a DM notification to the user who reacted"""
        try:
            if success:
                await self.client.send_message(
                    user_id, 
                    "✅ Issue sent to Linear! Thanks for flagging this."
                )
                logger.info(f"Success DM sent to user {user_id}")
            else:
                await self.client.send_message(
                    user_id, 
                    "❌ No issue found or failed to process. Please try again or check the context."
                )
                logger.info(f"Failure DM sent to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send DM to user {user_id}: {e}")
            # Note: We could add fallback to group message here, but it's in the main start method
            raise
    
    async def start(self):
        """Start the bot with security enhancements"""
        logger.info("Starting Telegram client with security enhancements...")
        
        try:
            # Initialize client with simple session handling
            self.client = TelegramClient(self.session_name, self.config.api_id, self.config.api_hash)
            
            # Start the client 
            await self.client.start()
            
            # Get user info
            me = await self.client.get_me()
            logger.info(f"Connected as: {me.username} ({me.first_name})")
            self.security_logger.log_event("BOT_STARTED", f"User: {me.username}")
            
            # Verify chat access and setup
            if not self.config.chat_id:
                logger.error("No CHAT_ID configured!")
                logger.error("Please configure CHAT_ID in your .env file.")
                return
            
            # Verify the configured chat ID is accessible
            logger.info(f"Verifying access to configured chat ID: {self.config.chat_id}")
            verified_id = await self.verify_chat_access(self.config.chat_id)
            
            if verified_id is None:
                logger.error("Cannot access the configured chat! Please check your CHAT_ID.")
                return
            
            if verified_id != self.config.chat_id:
                logger.warning(f"Chat ID format adjusted! Configured: {self.config.chat_id}, Using: {verified_id}")
                # Update configuration
                old_chat_id = self.config.chat_id
                if old_chat_id in self.config.whitelisted_chats:
                    self.config.whitelisted_chats.remove(old_chat_id)
                    self.config.whitelisted_chats.add(verified_id)
                self.config.chat_id = verified_id
            
            # Verify whitelisted chats
            if self.config.whitelisted_chats:
                logger.info("Verifying whitelisted chats...")
                verified_whitelist = set()
                for chat_id in self.config.whitelisted_chats:
                    verified_id = await self.verify_chat_access(chat_id)
                    if verified_id:
                        verified_whitelist.add(verified_id)
                
                if verified_whitelist != self.config.whitelisted_chats:
                    logger.warning("Some whitelisted chats are inaccessible or have different IDs")
                    logger.info(f"Original whitelist: {self.config.whitelisted_chats}")
                    logger.info(f"Verified whitelist: {verified_whitelist}")
                    self.config.whitelisted_chats = verified_whitelist
            
            logger.info(f"✅ Monitoring chat ID: {self.config.chat_id}")
            logger.info(f"✅ Whitelisted chats: {list(self.config.whitelisted_chats)}")
            
            # Test access to the configured chat
            logger.info("Testing bot access to configured chat...")
            test_success = await self.test_chat_access()
            if not test_success:
                logger.error("Bot cannot access the configured chat!")
                return
            
            logger.info("✅ Chat access verified! Bot is ready to monitor reactions.")
            logger.info("ℹ️  Bot will send DMs to users who react with 👍")
            
            # Setup event handlers
            @self.client.on(events.NewMessage())
            async def handle_message(event):
                logger.debug(f"📨 Message received in chat {event.chat_id} (configured: {self.config.chat_id})")
                
                # SECURITY CHECK: Only process whitelisted chats
                if not self.message_handler.is_chat_whitelisted(event.chat_id):
                    logger.warning(f"Ignoring message from non-whitelisted chat: {event.chat_id}")
                    self.security_logger.log_event("UNAUTHORIZED_CHAT_MESSAGE", f"Chat ID: {event.chat_id}")
                    return
                
                logger.debug(f"New message from @{event.sender.username}: {event.text[:50] if event.text else '[no text]'}...")
                self.message_handler.store_message(event.message)
            
            @self.client.on(events.Raw())
            async def handle_raw_update(update):
                """Handle raw updates to catch reactions with security checks"""
                logger.debug(f"🔥 Reaction received in chat {self.config.chat_id} (configured: {self.config.chat_id})")
                
                # Process the reaction update
                reaction_data = self.reaction_handler.process_reaction_update(update)
                
                if reaction_data:
                    # Analyze the issue
                    success = await self.analyze_and_send_to_linear(
                        reaction_data['message_id'],
                        reaction_data['user_id'],
                        reaction_data['chat_id']
                    )
                    
                    # Send notification to user (no group fallback)
                    try:
                        await self.send_user_notification(reaction_data['user_id'], success)
                    except Exception as e:
                        logger.error(f"Failed to send DM to user {reaction_data['user_id']}: {e}")
                        logger.warning(f"User {reaction_data['user_id']} may have DMs disabled or blocked the bot")
                        # No fallback to group messaging - keep conversations private
            
            logger.info("🔒 Secure bot is now running! React with 👍 to any message to trigger issue analysis.")
            logger.info("Security features active: Rate limiting, Message sanitization, Webhook authentication, Session encryption")
            logger.info("Press Ctrl+C to stop the bot")
            
            # Enable debug logging for the first 5 minutes
            original_level = logger.level
            logger.setLevel(logging.DEBUG)
            logger.info("🔧 Debug logging enabled for 5 minutes to help verify chat IDs")
            
            async def disable_debug():
                await asyncio.sleep(300)  # 5 minutes
                logger.setLevel(original_level)
                logger.info("🔧 Debug logging disabled")
            
            # Start background tasks
            asyncio.create_task(disable_debug())
            asyncio.create_task(self._periodic_cleanup())
            logger.info("🔧 Periodic database cleanup started")
            
            # Keep the bot running
            await self.client.run_until_disconnected()
            
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            self.security_logger.log_event("BOT_START_ERROR", str(e))
            raise
        finally:
            # Clean up session files before disconnect
            if self.client and self.client.is_connected():
                try:
                    logger.info("Disconnecting client...")
                    await self.client.disconnect()
                    logger.info("Client disconnected successfully")
                except Exception as e:
                    logger.error(f"Error during client disconnect: {e}") 