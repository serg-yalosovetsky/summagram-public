import asyncio
from loguru import logger
from shared.config import Config
from telethon import TelegramClient


async def auth():
    logger.info(f"Connecting to Telegram with API ID: {Config.TELEGRAM_API_ID}")
    client = TelegramClient(
        "summagram_session", Config.TELEGRAM_API_ID, Config.TELEGRAM_API_HASH
    )
    await client.start(phone=Config.TELEGRAM_PHONE)
    logger.success(
        "Authentication successful! Session saved to 'summagram_session.session'"
    )
    await client.disconnect()


if __name__ == "__main__":
    if not Config.TELEGRAM_API_ID or not Config.TELEGRAM_API_HASH:
        logger.error(
            "TELEGRAM_API_ID or TELEGRAM_API_HASH not set in .env or config.py"
        )
        logger.info("Please fetch them from https://my.telegram.org/apps")
    else:
        asyncio.run(auth())
