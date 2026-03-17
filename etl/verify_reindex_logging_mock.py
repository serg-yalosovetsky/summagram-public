import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "etl"))

# Use a mock logger if loguru is not installed, or try to import it
try:
    from loguru import logger
except ImportError:

    class MockLogger:
        def info(self, msg):
            print(f"INFO: {msg}")

        def warning(self, msg):
            print(f"WARNING: {msg}")

        def error(self, msg):
            print(f"ERROR: {msg}")

        def remove(self):
            pass

        def add(self, *args, **kwargs):
            pass

    logger = MockLogger()


# Mock Config if needed
class Config:
    DB_PATH = "summagram.db"
    LLM_API_BASE = "http://localhost:11434/v1"


# Mock models if needed or import
try:
    from etl.models import TelegramMediaMetadata
except ImportError:
    # Need pydantic
    try:
        from pydantic import BaseModel

        class TelegramMediaMetadata(BaseModel):
            type: str
            path: str | None = None
            description: str | None = None
            url: str | None = None
            is_meme: bool | None = None
            is_portrait: bool | None = None
            tags: str | None = None

            def model_dump(self, **kwargs):
                return self.dict(**kwargs)
    except ImportError:
        print("Pydantic not installed, cannot run test properly")
        sys.exit(1)

# Import the class to test - we need to patch imports that might fail
# We can't easily patch imports inside the module from here without complex mocking
# But let's try to run it assuming dependencies are there or we mock them

# Let's mock aiosqlite and others
sys.modules["aiosqlite"] = type("Mock", (), {"connect": lambda *args: None})
sys.modules["httpx"] = type(
    "Mock",
    (),
    {
        "AsyncClient": lambda *args: None,
        "RequestError": Exception,
        "HTTPStatusError": Exception,
    },
)
sys.modules["tenacity"] = type(
    "Mock",
    (),
    {
        "retry": lambda *args, **kwargs: lambda f: f,
        "stop_after_attempt": lambda *args: None,
        "wait_fixed": lambda *args: None,
        "retry_if_exception_type": lambda *args: None,
    },
)

# Now import the source
# We need to make sure 'sources' and 'models' are importable
from etl.sources.media_reindex_source import MediaReindexSource  # noqa: E402


async def test_missing_path_logging():
    # Patch logger in the module
    import etl.sources.media_reindex_source as module

    module.logger = logger

    source = MediaReindexSource()

    # Create valid metadata but missing path
    media = TelegramMediaMetadata(
        type="photo",
        description="Test photo",
        path=None,  # Missing path
        url="http://example.com/photo.jpg",
    )

    print("Testing _reanalyze_photo with missing path...")
    result = await source._reanalyze_photo(media, "doc_123")

    print(f"Result returned: {result}")

    # Test audio
    media_audio = TelegramMediaMetadata(type="audio", path="/non/existent/path.mp3")
    print("\nTesting _reanalyze_audio with non-existent path...")
    result_audio = await source._reanalyze_audio(media_audio, "doc_456")
    print(f"Result returned: {result_audio}")


if __name__ == "__main__":
    asyncio.run(test_missing_path_logging())
