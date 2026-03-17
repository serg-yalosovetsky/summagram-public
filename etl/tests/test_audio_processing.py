import unittest
import pytest

pytestmark = pytest.mark.unit
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone
import os

# Add project root to path


from etl.sources.telegram import TelegramSource  # noqa: E402
# etl_dir is added to path in conftest, so we can import from models directly
from models import GenericDocument  # noqa: E402


class TestAudioProcessing(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        with patch("etl.sources.telegram.TelegramClient"):
            self.source = TelegramSource(session_name="test_session")
        self.source.client = MagicMock()

    async def test_audio_processing_integration(self):
        # 1. Setup Mock Message
        mock_msg = MagicMock()
        mock_msg.id = 12345
        mock_msg.date = datetime.now(timezone.utc)
        mock_msg.message = "Hello world"
        mock_msg.out = False
        mock_msg.reply_to = None
        mock_msg.forward = (
            None  # Explicitly set forward to None to avoid MagicMock issues
        )

        # Mock Sender
        mock_sender = MagicMock()
        mock_sender.id = 999
        mock_sender.first_name = "Test"
        mock_sender.last_name = "User"
        mock_sender.username = "testuser"
        mock_msg.get_sender = AsyncMock(return_value=mock_sender)

        # Mock Client Download
        self.source.client.download_media = AsyncMock(return_value="/tmp/test.ogg")

        # Mock Media
        from telethon.tl.types import (
            MessageMediaDocument,
            Document,
            DocumentAttributeAudio,
        )

        mock_attr = DocumentAttributeAudio(duration=10, voice=True)
        mock_doc = Document(
            id=1,
            access_hash=1,
            file_reference=b"",
            date=mock_msg.date,
            mime_type="audio/ogg",
            size=100,
            dc_id=1,
            attributes=[mock_attr],
        )
        mock_msg.media = MessageMediaDocument(document=mock_doc)

        # (Mock results no longer needed since transcription is deferred)

        # 2. Run _msg_to_doc
        doc = await self.source._msg_to_doc(mock_msg, 6789, "Test Chat")

        # 3. Assertions
        self.assertIsInstance(doc, GenericDocument)
        # It should format it as [VOICE]
        self.assertIn("[VOICE]", doc.content)
        self.assertIn("Hello world", doc.content)
        self.assertEqual(doc.metadata["media"]["type"], "voice")
        self.assertEqual(doc.metadata["media"]["duration"], 10.0)

        self.source.client.download_media.assert_called_once()


if __name__ == "__main__":
    unittest.main()
