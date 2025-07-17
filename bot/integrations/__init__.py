"""
External integrations including OpenAI and webhook functionality.
"""

try:
    from .openai_client import OpenAIClient
except ImportError:
    OpenAIClient = None

from .webhook import WebhookClient 