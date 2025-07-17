"""
Reaction handling and processing functionality.
"""

import logging

logger = logging.getLogger(__name__)


class ReactionHandler:
    """Handle reaction processing and deduplication"""
    
    def __init__(self, config, security_logger, rate_limiter, persistence_manager=None):
        self.config = config
        self.security_logger = security_logger
        self.rate_limiter = rate_limiter
        self.persistence_manager = persistence_manager
        # Keep in-memory set for immediate deduplication + backward compatibility
        self.processed_reactions = set()
    
    def is_user_whitelisted(self, user_id):
        """Check if a user is whitelisted for emoji reactions"""
        if not self.config.whitelisted_users:
            logger.warning(f"No whitelisted users configured - blocking reaction from user {user_id}")
            return False
        return user_id in self.config.whitelisted_users
    
    def is_chat_whitelisted(self, chat_id):
        """Check if a chat is whitelisted for bot operations"""
        if not self.config.whitelisted_chats:
            # If no whitelist is configured, only allow the primary chat
            return chat_id == self.config.chat_id
        return chat_id in self.config.whitelisted_chats
    
    def process_reaction_update(self, update):
        """Process a reaction update and extract relevant information"""
        # Check if this is a reaction update
        if not hasattr(update, 'CONSTRUCTOR_ID') or update.CONSTRUCTOR_ID != 0x5e1b3cb8:
            return None
        
        chat_id = getattr(update, 'peer', None)
        if not chat_id:
            return None
        
        # Convert peer to chat ID
        if hasattr(chat_id, 'chat_id'):
            actual_chat_id = -chat_id.chat_id  # Groups are negative
        elif hasattr(chat_id, 'channel_id'):
            actual_chat_id = -1000000000000 - chat_id.channel_id  # Channels/supergroups
        elif hasattr(chat_id, 'user_id'):
            actual_chat_id = chat_id.user_id  # Private chats
        else:
            return None
        
        # SECURITY CHECK: Only process whitelisted chats
        if not self.is_chat_whitelisted(actual_chat_id):
            logger.warning(f"Ignoring reaction from non-whitelisted chat: {actual_chat_id}")
            self.security_logger.log_event("UNAUTHORIZED_CHAT_REACTION", f"Chat ID: {actual_chat_id}")
            return None
        
        msg_id = getattr(update, 'msg_id', None)
        reactions = getattr(update, 'reactions', None)
        
        if not msg_id or not reactions:
            return None
        
        # Check for 👍 emoji reaction (supported reaction)
        for result in reactions.results:
            if hasattr(result, 'reaction') and hasattr(result.reaction, 'emoticon'):
                if result.reaction.emoticon == '👍':
                    logger.info(f"👍 reaction detected! Processing issue analysis...")
                    
                    # Create unique identifier for this reaction to prevent duplicates
                    reaction_key = f"{actual_chat_id}_{msg_id}_{result.reaction.emoticon}"
                    
                    # Check if we've already processed this reaction (persistent storage first)
                    if self.persistence_manager and self.persistence_manager.is_reaction_processed(reaction_key):
                        logger.debug(f"Reaction already processed (persistent): {reaction_key}")
                        return None
                    
                    # Check if we've already processed this reaction (in-memory cache)
                    if reaction_key in self.processed_reactions:
                        logger.debug(f"Reaction already processed (memory): {reaction_key}")
                        return None
                    
                    # Get user ID from recent_reactions (correct path)
                    user_id = None
                    if hasattr(reactions, 'recent_reactions') and reactions.recent_reactions:
                        for reaction in reactions.recent_reactions:
                            if hasattr(reaction, 'reaction') and hasattr(reaction.reaction, 'emoticon'):
                                if reaction.reaction.emoticon == '👍':
                                    if hasattr(reaction, 'peer_id') and hasattr(reaction.peer_id, 'user_id'):
                                        user_id = reaction.peer_id.user_id
                                        break
                    
                    if user_id is None:
                        logger.warning("Could not identify user who reacted")
                        return None
                    
                    # SECURITY CHECK: Only process whitelisted users
                    if not self.is_user_whitelisted(user_id):
                        logger.warning(f"Ignoring reaction from non-whitelisted user: {user_id}")
                        self.security_logger.log_event("UNAUTHORIZED_USER_REACTION", f"User ID: {user_id}")
                        return None
                    
                    # Rate limiting check
                    if not self.rate_limiter.is_allowed(user_id):
                        logger.warning(f"Rate limit exceeded for user {user_id}")
                        self.security_logger.log_event("RATE_LIMIT_EXCEEDED", f"User: {user_id}", user_id)
                        return None
                    
                    # Mark this reaction as processed (both persistent and in-memory)
                    self.processed_reactions.add(reaction_key)
                    
                    if self.persistence_manager:
                        self.persistence_manager.mark_reaction_processed(
                            reaction_key,
                            actual_chat_id,
                            msg_id,
                            user_id,
                            result.reaction.emoticon
                        )
                    
                    # Cleanup old processed reactions (keep last 1000 to prevent memory issues)
                    if len(self.processed_reactions) > 1000:
                        # Keep only the most recent 500 reactions
                        self.processed_reactions = set(list(self.processed_reactions)[-500:])
                        logger.debug("Cleaned up old processed reactions")
                    
                    logger.info(f"Processing reaction from whitelisted user: {user_id}")
                    
                    return {
                        'message_id': msg_id,
                        'user_id': user_id,
                        'chat_id': actual_chat_id,
                        'reaction_key': reaction_key
                    }
        
        return None 