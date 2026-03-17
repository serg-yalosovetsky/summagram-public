import sys
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.append(os.getcwd())

# Mock dependencies that might be missing in this environment
import asyncio
from unittest.mock import patch
from sources.telegram import TelegramSource
from etl.processing.telegram_etl import transform_telegram_docs_to_nodes


@patch("sources.telegram.Config")
@patch("sources.telegram.TelegramClient")
async def test_metadata_extraction(mock_client_class, mock_config):
    mock_config.TELEGRAM_API_ID = 123
    mock_config.TELEGRAM_API_HASH = "abc"
    mock_config.TELEGRAM_PHONE = "123"

    source = TelegramSource()

    # Mock Telethon Message
    mock_msg = MagicMock()
    mock_msg.id = 12345
    mock_msg.message = "Hello, this is a forwarded message"
    mock_msg.date = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    mock_msg.out = False
    mock_msg.reply_to = None

    # Mock Sender
    mock_sender = MagicMock()
    mock_sender.id = 111
    mock_sender.first_name = "Alex"
    mock_sender.last_name = ""
    mock_sender.username = "alex_user"
    mock_get_sender = AsyncMock(return_value=mock_sender)
    mock_msg.get_sender = mock_get_sender

    # Mock Forwarding
    mock_fwd = MagicMock()
    mock_fwd.sender_id = 999
    mock_fwd.from_name = None
    # Ensure hasattr(fwd, 'original_fwd') is False for the simple case
    del mock_fwd.original_fwd

    mock_fwd_entity = MagicMock()
    mock_fwd_entity.first_name = "Media"
    mock_fwd_entity.last_name = "Rater"
    mock_fwd_entity.username = "mediarater"
    mock_msg.get_forward_from = AsyncMock(return_value=mock_fwd_entity)

    mock_msg.forward = mock_fwd

    doc = await source._msg_to_doc(mock_msg, chat_id=777, chat_title="Lev")

    print("\n--- Document Mapping ---")
    print(f"Content: {doc.content}")
    print(f"Metadata: {doc.metadata}")

    # Verify Document
    assert "Alex -> Lev (Forwarded from Media Rater)" in doc.content
    assert doc.metadata["sender_name"] == "Alex"
    assert doc.metadata["recipient_name"] == "Lev"
    assert doc.metadata["forward_from_name"] == "Media Rater"

    # Test ETL Transformation
    nodes = transform_telegram_docs_to_nodes([doc])
    node = nodes[0]

    print("\n--- Node Metadata ---")
    print(node.metadata)

    assert node.metadata["author"] == "Alex"
    assert node.metadata["recipient"] == "Lev"
    assert node.metadata["forwarded_from"] == "Media Rater"

    print("\nMetadata Extraction Test PASSED!")


if __name__ == "__main__":
    asyncio.run(test_metadata_extraction())
