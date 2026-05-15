#!/usr/bin/env python3
"""Main entry point for XianyuAutoAgent.

This module initializes and runs the Xianyu auto-reply agent,
handling WebSocket connections and message processing.
"""

import asyncio
import json
import os
import time
import random
from loguru import logger
from dotenv import load_dotenv

from XianyuApis import XianyuApis
from XianyuAgent import XianyuReplyBot

# Load environment variables
load_dotenv()


def get_env_or_raise(key: str) -> str:
    """Get an environment variable or raise an error if not set."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(f"Required environment variable '{key}' is not set.")
    return value


async def main():
    """Main async function to run the XianyuAutoAgent."""
    # Load configuration from environment
    cookies_str = get_env_or_raise("COOKIES_STR")
    heartbeat_interval = int(os.getenv("HEARTBEAT_INTERVAL", "15"))
    ai_model = os.getenv("AI_MODEL", "qwen-max")

    logger.info("Initializing XianyuAutoAgent...")

    # Initialize API client
    xianyu_api = XianyuApis()

    # Check login status
    if not xianyu_api.hasLogin():
        logger.error("Not logged in. Please check your COOKIES_STR in .env")
        return

    logger.info("Login verified successfully.")

    # Initialize the reply bot
    bot = XianyuReplyBot()

    # Get user info for WebSocket connection
    user_info = xianyu_api.get_user_info()
    if not user_info:
        logger.error("Failed to retrieve user info.")
        return

    user_id = user_info.get("userId", "")
    logger.info(f"Logged in as user: {user_id}")

    # Main loop — reconnect on disconnect
    while True:
        try:
            logger.info("Connecting to Xianyu WebSocket...")
            await run_websocket_loop(xianyu_api, bot, heartbeat_interval)
        except KeyboardInterrupt:
            logger.info("Shutting down XianyuAutoAgent.")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            # Increased max wait time to 30s to be less aggressive on reconnects
            wait_time = random.uniform(5, 30)
            logger.info(f"Reconnecting in {wait_time:.1f} seconds...")
            await asyncio.sleep(wait_time)


async def run_websocket_loop(
    xianyu_api: XianyuApis,
    bot: XianyuReplyBot,
    heartbeat_interval: int,
):
    """Run the WebSocket event loop for receiving and replying to messages.

    Args:
        xianyu_api: Initialized XianyuApis instance.
        bot: Initialized XianyuReplyBot instance.
        heartbeat_interval: Seconds between heartbeat pings.
    """
    ws = await xianyu_api.get_websocket()
    if ws is None:
        raise ConnectionError("Failed to establish WebSocket connection.")

    logger.info("WebSocket connection established.")
    last_heartbeat = time.time()

    async for message in ws:
        now = time.time()

        # Send heartbeat if interval has elapsed
        if now - last_heartbeat >= heartbeat_interval:
            await ws.ping()
            last_heartbeat = now
         