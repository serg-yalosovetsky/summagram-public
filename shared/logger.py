import os
import sys
from datetime import datetime
from loguru import logger


def setup_logger(service_name: str):
    """
    Configures loguru to log to both stdout and a rotating file.
    Logs are stored in the repository's logs directory.
    """
    # Remove default handler
    logger.remove()

    # Add stdout handler
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
    )

    # Ensure logs directory exists
    log_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
    )
    os.makedirs(log_dir, exist_ok=True)

    # Create file handler with separate file each run as well as daily rotation
    # E.g. logs/backend_2026-03-05_02-31-00.log
    # This fulfills requirement: separate log file for each server as docker compose is up or down
    start_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(log_dir, f"{service_name}_{start_time}.log")

    logger.add(
        log_file,
        rotation="1 day",  # new file each day (though it will start a new one on restart anyway)
        retention="30 days",  # automatically delete if too old
        compression="zip",  # compress older files
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )

    return logger
