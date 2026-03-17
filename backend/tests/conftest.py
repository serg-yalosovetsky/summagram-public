import pytest
import asyncio
import pytest_asyncio
import os
from pathlib import Path
import sys
import importlib.util
from unittest.mock import MagicMock, AsyncMock, patch

# Service directory
backend_dir = str(Path(__file__).resolve().parent.parent)
# Project root
root = str(Path(__file__).resolve().parent.parent.parent)

# Safely isolate sys.path
# Remove root and other service directories to avoid collisions
for p in list(sys.path):
    is_project_path = p == root or p == "" or p == "." or p.startswith(root)
    is_current_service = p == backend_dir
    is_venv = ".venv" in p
    is_root = p == root or p == "" or p == "."
    if is_project_path and not is_current_service and not is_venv and not is_root:
        while p in sys.path:
            sys.path.remove(p)

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Purge any incorrectly loaded local modules
local_modules = [
    "models",
    "schemas",
    "config",
    "database",
    "main",
    "inference",
    "telemetry",
]
for m in local_modules:
    if m in sys.modules:
        del sys.modules[m]

# Aggressively mock heavy modules BEFORE any local imports
mock_inf = MagicMock()
inference_instance = MagicMock()
inference_instance.initialize_embedding_model = (
    None  # optional, not awaited in lifespan
)
agent_response_json = '{"thought": "Responding to user.", "tool_call": null, "final_answer": "Mocked AI response"}'
inference_instance.generate_json = AsyncMock(return_value=agent_response_json)
inference_instance.generate_text = AsyncMock(return_value="Mocked AI response")
mock_inf.LocalInferenceService = MagicMock(return_value=inference_instance)
sys.modules["inference"] = mock_inf
mock_tel = MagicMock()
sys.modules["telemetry"] = mock_tel


# Global patch for StaticFiles to avoid "Directory does not exist" errors during collection/import
patch("fastapi.staticfiles.StaticFiles.__init__", return_value=None).start()

# Set LLM_SERVER_URL before loading main (session chat requires SGLang)
os.environ["LLM_SERVER_URL"] = "http://localhost:30000/v1"

# Patch setup_logger to avoid permission issues in tests
patch("shared.logger.setup_logger").start()

# Surgically import the backend main.py as 'backend_main'
spec = importlib.util.spec_from_file_location(
    "backend_main", os.path.join(backend_dir, "main.py")
)
backend_main = importlib.util.module_from_spec(spec)
sys.modules["backend_main"] = backend_main
spec.loader.exec_module(backend_main)

# Patch SGLang check so tests don't need a real SGLang server
patch.object(
    backend_main, "_check_sglang_reachable", new=AsyncMock(return_value=None)
).start()

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def mock_db_path():
    """Redirect POSTGRES_DSN to a temporary database for the entire test session."""
    from shared.config import Config

    original_dsn = Config.POSTGRES_DSN
    original_llm_api_key = Config.LLM_API_KEY
    original_llm_model = Config.LLM_MODEL
    Config.LLM_API_KEY = "dummy-test-key"
    Config.LLM_MODEL = "test-model"

    # We assume 'localhost' for tests since Postgres is exposed to host
    # and the container has a default db 'summagram'
    import asyncpg

    async def setup_db():
        try:
            # Connect to default postgres DB to create the test DB
            conn = await asyncpg.connect(
                "postgresql://summagram:fYfzQ9qdv2qLYYyD3jOF0z7yc2PyFVIFj57LrJI%2BJ50%3D@localhost:8432/postgres"
            )
            # Kill active connections to avoid deadlock
            await conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'test_summagram' AND pid <> pg_backend_pid();"
            )
            # Cannot run CREATE DATABASE inside a transaction block
            await conn.execute("DROP DATABASE IF EXISTS test_summagram")
            await conn.execute("CREATE DATABASE test_summagram")
            await conn.close()
        except OSError as e:
            import logging
            logging.getLogger("conftest").warning(
                f"Could not connect to test database container (Docker not running?): {e}. Skipping eager DB creation."
            )

    asyncio.run(setup_db())

    test_dsn = "postgresql://summagram:fYfzQ9qdv2qLYYyD3jOF0z7yc2PyFVIFj57LrJI%2BJ50%3D@localhost:8432/test_summagram"
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
    """FastAPI test client."""
    with TestClient(backend_main.app) as c:
        yield c


async def _mock_stream_messages(*args, **kwargs):
    """Async generator for stream_generate_text_from_messages mock."""
    for c in "Mocked AI response":
        yield c


@pytest.fixture(autouse=True)
def mock_inference_service():
    """Configure the already-mocked LocalInferenceService (patch where used: service and main)."""
    agent_response_json = '{"thought": "Responding to user.", "tool_call": null, "final_answer": "Mocked AI response"}'
    with (
        patch("backend.service.LocalInferenceService") as mock_svc,
        patch("backend.main.LocalInferenceService") as mock_main,
    ):
        instance = mock_svc.return_value
        mock_main.return_value = instance  # Point both to same instance
        instance.generate_text = AsyncMock(return_value="Mocked AI response")
        instance.generate_text_from_messages = AsyncMock(
            return_value="Mocked AI response"
        )
        instance.stream_generate_text_from_messages = _mock_stream_messages
        instance.generate_json = AsyncMock(return_value=agent_response_json)
        instance.analyze_image = AsyncMock(
            return_value={"description": "Mocked image analysis"}
        )
        instance.initialize_embedding_model = (
            lambda *args, **kwargs: None
        )  # Prevents NoneType error inside to_thread
        yield instance


@pytest.fixture(autouse=True)
def mock_session_agent():
    """Mock run_session_agent so session tests don't need SGLang. Patch where used (service imports it)."""
    with patch("backend.service.run_session_agent", new_callable=AsyncMock) as mock:
        mock.return_value = ("Mocked AI response", None)
        yield mock
