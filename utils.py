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
