"""Model Orchestrator — FastAPI application entry point.

Wires together configuration, state, middleware, routes, and the
startup/shutdown lifecycle. Business logic lives in dedicated modules:

- ``config.py``     — vLLM worker URL definitions
- ``models.py``     — shared application state
- ``services.py``   — sleep/wake mode switching & readiness polling
- ``middleware.py`` — reverse-proxy middleware
- ``router.py``     — route handlers
"""

import asyncio
from loguru import logger
from datetime import datetime
import sys
from pathlib import Path
from contextlib import asynccontextmanager

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from shared.logger import setup_logger  # noqa: E402

setup_logger("model_orchestrator")

from fastapi import FastAPI  # noqa: E402

from config import MODE_URLS  # noqa: E402
from middleware import ProxyMiddleware  # noqa: E402
from router import router  # noqa: E402
from services import startup_orchestrator, shutdown_orchestrator  # noqa: E402


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Model Orchestrator Startup at {datetime.now().isoformat()}...")
    logger.info(f"MODE_URLS: {MODE_URLS}")

    async def _bootstrap():
        try:
            await startup_orchestrator()
        except Exception as exc:
            logger.error(
                f"Error during startup initialisation: {exc}. "
                f"Workers will be woken on first request."
            )

    # Run bootstrap in background so the HTTP server starts immediately
    # and can pass the Docker healthcheck before vLLM is fully loaded.
    asyncio.create_task(_bootstrap())

    yield

    logger.info(f"Model Orchestrator Shutting Down at {datetime.now().isoformat()}...")
    try:
        await shutdown_orchestrator()
    except Exception as exc:
        logger.error(f"Error during shutdown: {exc}")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Model Orchestrator API Gateway",
    lifespan=lifespan,
)
app.add_middleware(ProxyMiddleware)
app.include_router(router)
