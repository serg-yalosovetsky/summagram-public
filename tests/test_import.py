from loguru import logger

try:
    import vllm

    logger.success("vllm imported successfully")
    logger.info(f"vllm location: {vllm.__file__}")
except ImportError as e:
    logger.error(f"Error: {e}")
