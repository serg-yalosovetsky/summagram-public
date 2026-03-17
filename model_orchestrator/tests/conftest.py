"""pytest configuration for model_orchestrator tests.

The Warm endpoint tests import `main`, which calls `setup_logger()` at module
level. In local dev the `logs/` directory is owned by Docker (root), so the
logger cannot create a file there. We patch `setup_logger` at its source
before any module that calls it is imported. Using `autouse=True` + session
scope ensures it fires exactly once, before collection.
"""

import sys
import types
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True, scope="session")
def _stub_logger_file_sink() -> None:  # type: ignore[return]  # generator fixture
    """Replace shared.logger.setup_logger with a no-op for tests.

    Must happen before `main` is imported, so we patch the module's attribute
    directly in `sys.modules` if already loaded, or pre-populate it as a stub
    so that `from shared.logger import setup_logger` inside main.py gets the mock.
    """
    # Pre-inject a mock `shared` package + `shared.logger` submodule if not present.
    if "shared" not in sys.modules:
        shared_pkg = types.ModuleType("shared")
        shared_pkg.__path__ = []  # type: ignore[attr-defined]
        sys.modules["shared"] = shared_pkg

    if "shared.logger" not in sys.modules:
        logger_mod = types.ModuleType("shared.logger")
        logger_mod.setup_logger = MagicMock()  # type: ignore[attr-defined]
        sys.modules["shared.logger"] = logger_mod
        sys.modules["shared"].logger = logger_mod  # type: ignore[attr-defined]
    else:
        # Already imported — patch in-place.
        sys.modules["shared.logger"].setup_logger = MagicMock()  # type: ignore[attr-defined]
