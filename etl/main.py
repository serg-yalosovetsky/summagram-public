from fastapi import FastAPI
from manager import JobManager
from etl.db.core import init_db
from contextlib import asynccontextmanager
from loguru import logger
import sys
from pathlib import Path
from datetime import datetime

# Add project root to sys.path to allow importing from sibling directories
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from shared.logger import setup_logger  # noqa: E402

setup_logger("etl")

from llm_setup import setup_llm_provider  # noqa: E402
from router import router  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from shared.config import Config  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"ETL Service Starting at {datetime.now().isoformat()}...")
    try:
        from shared.config import Config

        logger.info(f"ETL Config: {Config.get_safe_dict()}")
    except Exception as e:
        logger.warning(f"Failed to log ETL Config: {e}")
    await init_db()
    setup_llm_provider()

    # Initialize JobManager
    manager = JobManager()

    yield
    await manager.shutdown()
    logger.info(f"ETL Service Shutting Down at {datetime.now().isoformat()}...")


app = FastAPI(title="Summagram ETL Service", lifespan=lifespan)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
