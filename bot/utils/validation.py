"""
Validation utilities for API responses and data structures.
"""

import logging
from jsonschema import validate, ValidationError

logger = logging.getLogger(__name__)

# OpenAI response validation schema
OPENAI_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "maxLength": 200},
        "description": {"type": "string", "maxLength": 2000},
        "priority": {"type": "integer", "minimum": 1, "maximum": 4},
        "labels": {"type": "array", "items": {"type": "string"}},
        "related_messages": {"type": "array", "items": {"type": "string"}},
        "no_issue": {"type": "boolean"}
    },
    "anyOf": [
        {"required": ["title", "description", "priority"]},
        {"required": ["no_issue"]}
    ]
}


def validate_openai_response(response_data):
    """Validate OpenAI response structure"""
    try:
        validate(response_data, OPENAI_RESPONSE_SCHEMA)
        return True
    except ValidationError as e:
        logger.error(f"Invalid OpenAI response: {e}")
        return False 