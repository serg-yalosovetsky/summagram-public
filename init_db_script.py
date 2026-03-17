import asyncio
from loguru import logger
from database import init_db

if __name__ == "__main__":
    asyncio.run(init_db())
    logger.success("Database initialized successfully.")
