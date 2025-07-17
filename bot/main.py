"""
Main entry point for the Ellie Ticket Bot.
"""

import asyncio
import logging
from .core import SimpleIssueTracker
from .security import SecurityLogger

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main startup function"""
    try:
        tracker = SimpleIssueTracker()
        await tracker.start()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        # Log security event for crashes
        SecurityLogger().log_event("BOT_CRASH", str(e))
        raise


if __name__ == "__main__":
    asyncio.run(main()) 