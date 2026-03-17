import time
from datetime import datetime, timezone
from typing import Any
from contextlib import contextmanager
from loguru import logger
from functools import wraps


@contextmanager
def timer(name: str):
    start = time.perf_counter()
    logger.info(f"START: {name}")
    try:
        yield
    finally:
        end = time.perf_counter()
        logger.info(f"DONE: {name} took {end - start:.4f}s")


def monitor_perf(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with timer(f"Function {func.__name__}"):
            return func(*args, **kwargs)

    return wrapper


def monitor_perf_async(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        with timer(f"Async Function {func.__name__}"):
            return await func(*args, **kwargs)

    return wrapper


def format_sql(sql: str, params: tuple | list | None = None) -> str:
    """Render SQL with parameter placeholders replaced by actual values (for logging only)."""
    if not params:
        return sql.strip()
    result = sql
    for p in params:
        if p is None:
            replacement = "NULL"
        elif isinstance(p, str):
            replacement = f"'{p}'"
        else:
            replacement = str(p)
        result = result.replace("?", replacement, 1)
    return result.strip()


def parse_timestamp(value: Any) -> datetime:
    """Parse a timestamp into a UTC datetime object."""
    if isinstance(value, datetime):
        return value

    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
