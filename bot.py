#!/usr/bin/env python3
"""
Ellie Ticket Bot - A Telegram bot that monitors chat messages and creates Linear tickets when issues are detected.

This is a simple wrapper that imports from the new modular structure.
For the original monolithic code, see bot_legacy.py.
"""

import asyncio
from bot import main

if __name__ == "__main__":
    asyncio.run(main())