"""
Persistence manager for tracking processed messages and reactions.
"""

import sqlite3
import os
import stat
import logging
from datetime import datetime, timedelta
from typing import Optional, Set, List, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class PersistenceManager:
    """Manage persistent storage for bot state and processed data"""
    
    def __init__(self, db_path: str = "bot_state.db"):
        self.db_path = db_path
        self.init_database()
        self._secure_database_file()
    
    def init_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Table for processed messages
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_messages (
                    id INTEGER PRIMARY KEY,
                    message_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER,
                    timestamp DATETIME NOT NULL,
                    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(message_id, chat_id)
                )
            ''')
            
            # Table for processed reactions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_reactions (
                    id INTEGER PRIMARY KEY,
                    reaction_key TEXT NOT NULL UNIQUE,
                    chat_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    user_id INTEGER,
                    reaction_emoji TEXT NOT NULL,
                    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Table for bot state (last processed timestamps, etc.)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_state (
                    id INTEGER PRIMARY KEY,
                    key TEXT NOT NULL UNIQUE,
                    value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_processed_messages_chat_id ON processed_messages(chat_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_processed_messages_timestamp ON processed_messages(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_processed_reactions_chat_id ON processed_reactions(chat_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_processed_reactions_user_id ON processed_reactions(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_bot_state_key ON bot_state(key)')
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    def _secure_database_file(self):
        """Set secure permissions on database file"""
        try:
            # Set 600 permissions (owner read/write only)
            os.chmod(self.db_path, stat.S_IRUSR | stat.S_IWUSR)
            logger.debug(f"Secured database file permissions: {self.db_path}")
        except Exception as e:
            logger.warning(f"Could not secure database file permissions: {e}")
    
    @contextmanager
    def get_connection(self):
        """Get database connection with proper error handling"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def is_message_processed(self, message_id: int, chat_id: int) -> bool:
        """Check if a message has already been processed"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT 1 FROM processed_messages WHERE message_id = ? AND chat_id = ?',
                (message_id, chat_id)
            )
            return cursor.fetchone() is not None
    
    def mark_message_processed(self, message_id: int, chat_id: int, user_id: Optional[int] = None, timestamp: Optional[datetime] = None):
        """Mark a message as processed"""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT OR REPLACE INTO processed_messages 
                   (message_id, chat_id, user_id, timestamp) 
                   VALUES (?, ?, ?, ?)''',
                (message_id, chat_id, user_id, timestamp)
            )
            conn.commit()
            logger.debug(f"Marked message {message_id} in chat {chat_id} as processed")
    
    def is_reaction_processed(self, reaction_key: str) -> bool:
        """Check if a reaction has already been processed"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT 1 FROM processed_reactions WHERE reaction_key = ?',
                (reaction_key,)
            )
            return cursor.fetchone() is not None
    
    def mark_reaction_processed(self, reaction_key: str, chat_id: int, message_id: int, user_id: Optional[int] = None, reaction_emoji: str = "👍"):
        """Mark a reaction as processed"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT OR REPLACE INTO processed_reactions 
                   (reaction_key, chat_id, message_id, user_id, reaction_emoji) 
                   VALUES (?, ?, ?, ?, ?)''',
                (reaction_key, chat_id, message_id, user_id, reaction_emoji)
            )
            conn.commit()
            logger.debug(f"Marked reaction {reaction_key} as processed")
    
    def get_bot_state(self, key: str) -> Optional[str]:
        """Get a bot state value"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM bot_state WHERE key = ?', (key,))
            result = cursor.fetchone()
            return result['value'] if result else None
    
    def set_bot_state(self, key: str, value: str):
        """Set a bot state value"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT OR REPLACE INTO bot_state (key, value, updated_at) 
                   VALUES (?, ?, CURRENT_TIMESTAMP)''',
                (key, value)
            )
            conn.commit()
            logger.debug(f"Set bot state {key} = {value}")
    
    def get_last_processed_timestamp(self, chat_id: int) -> Optional[datetime]:
        """Get the last processed message timestamp for a chat"""
        timestamp_str = self.get_bot_state(f"last_processed_{chat_id}")
        if timestamp_str:
            try:
                return datetime.fromisoformat(timestamp_str)
            except ValueError:
                logger.warning(f"Invalid timestamp format in bot state: {timestamp_str}")
        return None
    
    def set_last_processed_timestamp(self, chat_id: int, timestamp: datetime):
        """Set the last processed message timestamp for a chat"""
        self.set_bot_state(f"last_processed_{chat_id}", timestamp.isoformat())
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old processed data to prevent database bloat"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Clean up old processed messages
            cursor.execute(
                'DELETE FROM processed_messages WHERE processed_at < ?',
                (cutoff_date,)
            )
            messages_deleted = cursor.rowcount
            
            # Clean up old processed reactions
            cursor.execute(
                'DELETE FROM processed_reactions WHERE processed_at < ?',
                (cutoff_date,)
            )
            reactions_deleted = cursor.rowcount
            
            conn.commit()
            
            if messages_deleted > 0 or reactions_deleted > 0:
                logger.info(f"Cleaned up {messages_deleted} old processed messages and {reactions_deleted} old processed reactions")
    
    def get_processed_messages_count(self, chat_id: Optional[int] = None) -> int:
        """Get count of processed messages"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if chat_id:
                cursor.execute('SELECT COUNT(*) FROM processed_messages WHERE chat_id = ?', (chat_id,))
            else:
                cursor.execute('SELECT COUNT(*) FROM processed_messages')
            return cursor.fetchone()[0]
    
    def get_processed_reactions_count(self, chat_id: Optional[int] = None) -> int:
        """Get count of processed reactions"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if chat_id:
                cursor.execute('SELECT COUNT(*) FROM processed_reactions WHERE chat_id = ?', (chat_id,))
            else:
                cursor.execute('SELECT COUNT(*) FROM processed_reactions')
            return cursor.fetchone()[0]
    
    def get_recent_processed_messages(self, chat_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent processed messages for a chat"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT message_id, chat_id, user_id, timestamp, processed_at 
                   FROM processed_messages 
                   WHERE chat_id = ? 
                   ORDER BY timestamp DESC 
                   LIMIT ?''',
                (chat_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def vacuum_database(self):
        """Optimize database by reclaiming space"""
        with self.get_connection() as conn:
            conn.execute('VACUUM')
            logger.info("Database vacuumed successfully")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get table sizes
            cursor.execute('SELECT COUNT(*) FROM processed_messages')
            messages_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM processed_reactions')
            reactions_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM bot_state')
            state_count = cursor.fetchone()[0]
            
            # Get database file size
            try:
                file_size = os.path.getsize(self.db_path)
            except OSError:
                file_size = 0
            
            return {
                'processed_messages': messages_count,
                'processed_reactions': reactions_count,
                'bot_state_entries': state_count,
                'database_size_bytes': file_size,
                'database_path': self.db_path
            } 