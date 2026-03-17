import pytest
import asyncio
import pytest_asyncio
import os
from pathlib import Path
import sys
import importlib.util
from unittest.mock import MagicMock, AsyncMock, patch

# Service directory
etl_dir = str(Path(__file__).resolve().parent.parent)
# Project root
root = str(Path(__file__).resolve().parent.parent.parent)

# Safely isolate sys.path
# Remove root and other service directories to avoid collisions
for p in list(sys.path):
    is_project_path = p == root or p == "" or p == "." or p.startswith(root)
    is_current_service = p == etl_dir
    is_venv = ".venv" in p
    is_root = p == root or p == "" or p == "."
    if is_project_path and not is_current_service and not is_venv and not is_root:
        while p in sys.path:
            sys.path.remove(p)

if etl_dir not in sys.path:
    sys.path.insert(0, etl_dir)

# Purge any incorrectly loaded local modules
local_modules = [
    "models",
    "schemas",
    "config",
    "database",
    "main",
    "sources",
    "processing",
    "manager",
    "llm_config",
    "telemetry",
]
for m in local_modules:
    if m in sys.modules:
        del sys.modules[m]

# Aggressively mock heavy modules
sys.modules["llm_config"] = MagicMock()
sys.modules["telemetry"] = MagicMock()

# Patch setup_logger to avoid permission issues in tests
patch("shared.logger.setup_logger").start()

# Surgically import the etl main.py as 'etl_main'
spec = importlib.util.spec_from_file_location(
    "etl_main", os.path.join(etl_dir, "main.py")
)
etl_main = importlib.util.module_from_spec(spec)
sys.modules["etl_main"] = etl_main
spec.loader.exec_module(etl_main)

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def mock_db_path():
    """Redirect POSTGRES_DSN to a temporary database for the entire test session."""
    from shared.config import Config

    original_dsn = Config.POSTGRES_DSN
    original_llm_api_key = getattr(Config, "LLM_API_KEY", None)
    original_llm_model = getattr(Config, "LLM_MODEL", None)
    original_telegram_api_id = getattr(Config, "TELEGRAM_API_ID", None)
    original_telegram_api_hash = getattr(Config, "TELEGRAM_API_HASH", None)
    
    Config.LLM_API_KEY = "dummy-test-key"
    Config.LLM_MODEL = "test-model"
    Config.TELEGRAM_API_ID = "12345"
    Config.TELEGRAM_API_HASH = "dummy-hash"

    import asyncpg

    async def setup_db():
        conn = await asyncpg.connect(
            "postgresql://summagram:fYfzQ9qdv2qLYYyD3jOF0z7yc2PyFVIFj57LrJI%2BJ50%3D@localhost:8432/postgres"
        )
        await conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'test_summagram_etl' AND pid <> pg_backend_pid();"
        )
        await conn.execute("DROP DATABASE IF EXISTS test_summagram_etl")
        await conn.execute("CREATE DATABASE test_summagram_etl")
        await conn.close()

    asyncio.run(setup_db())

    test_dsn = "postgresql://summagram:fYfzQ9qdv2qLYYyD3jOF0z7yc2PyFVIFj57LrJI%2BJ50%3D@localhost:8432/test_summagram_etl"
    Config.POSTGRES_DSN = test_dsn
    yield test_dsn
    Config.POSTGRES_DSN = original_dsn


@pytest_asyncio.fixture(scope="session")
async def db_init(mock_db_path):
    """Initialize the database schema and migrate it."""
    import subprocess
    os.environ["PICCOLO_CONF"] = "piccolo_conf"
    os.environ["POSTGRES_DSN"] = mock_db_path
    
    subprocess.run(
        ["uv", "run", "piccolo", "migrations", "forwards", "all"],
        cwd=root,
        check=True,
        env=os.environ
    )
    
    import etl.db.core
    await etl.db.core.init_db()
    return mock_db_path


@pytest.fixture
def client(db_init):
    """FastAPI test client for ETL."""
    with TestClient(etl_main.app) as c:
        yield c


@pytest.fixture(autouse=True)
def mock_job_manager():
    """Mock JobManager to avoid actually starting long jobs."""
    with patch("router.JobManager") as mock:
        instance = mock.return_value
        instance.sources = {"telegram": MagicMock(), "reindex_media": MagicMock()}
        instance.submit_job = AsyncMock(return_value="test-job-id")
        instance.get_job = MagicMock(
            return_value={
                "job_id": "test-job-id",
                "status": "processing",
                "progress": 0.5,
                "message": "Processing...",
            }
        )
        yield instance
