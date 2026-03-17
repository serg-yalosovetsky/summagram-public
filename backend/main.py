import asyncio
from datetime import datetime
import gc
from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger
import uvicorn
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import torch
import sys
from pathlib import Path

# Add project root to sys.path to allow importing from sibling directories (like etl)
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from shared.config import Config  # noqa: E402
from shared.logger import setup_logger  # noqa: E402

setup_logger("backend")

from inference import LocalInferenceService  # noqa: E402
from backend.scheduler import ModelScheduler  # noqa: E402
from telemetry import init_telemetry  # noqa: E402
from routes import router as api_router  # noqa: E402


async def _check_sglang_reachable() -> None:
    """Verify SGLang server is reachable. Retries with backoff until ready or max attempts."""
    url = Config.LLM_SERVER_URL
    if not url or not url.strip():
        raise RuntimeError(
            "LLM_SERVER_URL is not set. Session chat requires SGLang. "
            "Set LLM_SERVER_URL (e.g. http://sglang:30000/v1) and ensure SGLang is running."
        )
    import httpx

    max_attempts = 60  # ~5 min with 5s interval
    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(url.rstrip("/") + "/models")
                r.raise_for_status()
            logger.info(f"SGLang server reachable at {url}")
            return
        except Exception as e:
            if attempt == max_attempts:
                raise RuntimeError(
                    f"SGLang server unreachable at {url}. Session chat requires SGLang. "
                    f"Ensure SGLang is running and LLM_SERVER_URL is correct. Error: {e}"
                ) from e
            delay = min(5 * attempt, 15)
            logger.info(
                f"SGLang not ready at url {url} (attempt {attempt}/{max_attempts}), retrying in {delay}s: {e}"
            )
            await asyncio.sleep(delay)


# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Backend Service Starting at {datetime.now().isoformat()}...")
    logger.info(f"Backend Config: {Config.get_safe_dict()}")
    init_telemetry()

    await _check_sglang_reachable()

    service = LocalInferenceService()
    try:
        # Pre-load embedding model in background (text inference via SGLang, no in-process model)
        asyncio.create_task(asyncio.to_thread(service.initialize_embedding_model))
    except Exception as e:
        logger.error(f"Failed to initialize models: {e}")

    scheduler = ModelScheduler()
    await scheduler.start()
    app.state.scheduler = scheduler

    yield
    logger.info(f"Backend Service Shutting Down at {datetime.now().isoformat()}...")
    await scheduler.stop()
    # Release model references (vision, audio, embeddings)
    service.shutdown()
    # Force garbage collection
    gc.collect()
    # Clear CUDA cache if available
    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception as e:
        logger.warning(f"CUDA cache clear failed (non-fatal): {e}")


app = FastAPI(title="Summagram Backend", version="1.0.0", lifespan=lifespan)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Static Files (Media) ---
app.mount("/media", StaticFiles(directory="/app/storage/media"), name="media")

# --- Include Routers ---
app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
