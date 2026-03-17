import time
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


def time_str_to_seconds(time_str: str) -> int:
    """Превращает '01:30' или '01:05:30' в секунды."""
    parts = list(map(int, time_str.split(":")))
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    elif len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return 0


def seconds_to_time_str(seconds: int) -> str:
    """Превращает секунды обратно в формат 'MM:SS' (или HH:MM:SS, если длинное)."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
