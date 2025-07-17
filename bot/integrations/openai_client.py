"""
OpenAI integration for issue analysis.
"""

import json
import logging
from datetime import datetime

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AsyncOpenAI = None

from ..utils.validation import validate_openai_response
from ..utils.helpers import sanitize_message, anonymize_username

logger = logging.getLogger(__name__)


class OpenAIClient:
    """OpenAI integration for issue analysis"""
    
    def __init__(self, api_key, security_logger, anonymize_usernames=True):
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI library not installed. Install with: pip install openai==1.54.4")
        
        self.client = AsyncOpenAI(api_key=api_key)
        self.security_logger = security_logger
        self.anonymize_usernames = anonymize_usernames
    
    async def analyze_issue(self, trigger_message, context_messages, user_id):
        """Analyze context and determine if there's a valid issue"""
        logger.warning("OpenAI analysis is deprecated - this should be handled by n8n webhook")
        
        if not OPENAI_AVAILABLE:
            logger.error("OpenAI not available - processing should be handled by n8n")
            return None
        
        try:
            # Create context string for LLM with sanitized data
            context = f"TRIGGER MESSAGE:\n@{self._anonymize_username(trigger_message['username'])}: {trigger_message['text']}\n\n"
            context += "RECENT CONTEXT:\n"
            for msg in context_messages:
                context += f"@{self._anonymize_username(msg['username'])}: {msg['text']}\n"
            
            logger.info("Sending sanitized context to OpenAI for analysis...")
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": """Analyze this chat for technical issues. Create a Linear issue ticket.
                        
                        Return JSON with:
                        {
                            "title": "Brief issue title",
                            "description": "Detailed description with context from messages",
                            "priority": 1-4 (1=urgent, 4=low),
                            "labels": ["bug", "user-report"],
                            "related_messages": ["relevant message texts"]
                        }
                        
                        Only return valid JSON. If no real issue found, return: {"no_issue": true}
                        
                        IMPORTANT: The usernames and some data may be anonymized for privacy."""
                    },
                    {"role": "user", "content": context}
                ],
                temperature=0.1,
                max_tokens=1000  # Limit response size
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"OpenAI analysis result: {result}")
            
            # Validate response structure
            if not validate_openai_response(result):
                logger.error("OpenAI response failed validation")
                self.security_logger.log_event("OPENAI_RESPONSE_INVALID", "Response failed validation", user_id)
                return None
            
            if result.get("no_issue"):
                logger.info("No valid issue detected by AI")
                return None
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from OpenAI: {e}")
            self.security_logger.log_event("OPENAI_JSON_ERROR", str(e), user_id)
            return None
        except Exception as e:
            logger.error(f"Error processing issue with OpenAI: {e}")
            self.security_logger.log_event("OPENAI_ERROR", str(e), user_id)
            return None
    
    def _anonymize_username(self, username):
        """Anonymize username if enabled"""
        return anonymize_username(username, self.anonymize_usernames) 