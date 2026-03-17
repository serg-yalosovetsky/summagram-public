import os
import sys
import unittest
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

pytestmark = [pytest.mark.unit, pytest.mark.integration]

import chromadb  # noqa: E402
chromadb.HttpClient = MagicMock()


sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "backend"))

try:
    from backend.inference import LocalInferenceService  # noqa: E402
except ImportError as e:
    pytest.skip(f"Skipping inference tests: {e}", allow_module_level=True)


class TestInferenceLogic(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = LocalInferenceService()
        self.audio_client_mock = MagicMock()
        self.service.audio_client = self.audio_client_mock

    async def test_transcribe_audio_returns_metadata(self):
        mock_response = MagicMock()
        mock_response.text = (
            "Hello world this is a test message to ensure cleanup triggers"
        )
        mock_response.language = "en"
        mock_response.duration = 2.5

        self.audio_client_mock.audio.transcriptions.create = AsyncMock(
            return_value=mock_response
        )

        self.service.generate_text = AsyncMock(return_value="Cleaned Hello world")

        with patch(
            "builtins.open", unittest.mock.mock_open(read_data=b"dummy audio data")
        ):
            result = await self.service.transcribe_audio("test.mp3")

        self.assertTrue(hasattr(result, "transcript"))
        self.assertEqual(
            result.transcript,
            "Hello world this is a test message to ensure cleanup triggers",
        )
        self.assertEqual(result.language, "en")
        self.assertEqual(result.duration, 2.5)
        self.assertEqual(result.cleaned_transcript, "Cleaned Hello world")


if __name__ == "__main__":
    unittest.main()
