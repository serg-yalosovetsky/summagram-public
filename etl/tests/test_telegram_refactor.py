import sys
import os
import json
from datetime import datetime


# Mock security to avoid import issues
class MockSecurity:
    @staticmethod
    def mask_pii(text):
        return text


sys.modules["security"] = MockSecurity

# Add project root to path
sys.path.append(os.getcwd())

from etl.models import GenericDocument  # noqa: E402
from etl.processing.telegram_etl import transform_telegram_docs_to_nodes  # noqa: E402


def test_refactor():
    docs = [
        GenericDocument(
            source_id="telegram_123",
            doc_id="1",
            content="Hello world",
            timestamp=datetime.now(),
            metadata={
                "sender_name": "Alice",
                "chat_id": 123,
                "chat_title": "Test Chat",
                "is_from_me": False,
            },
        ),
        GenericDocument(
            source_id="telegram_123",
            doc_id="2",
            content="How are you?",
            timestamp=datetime.now(),
            metadata={
                "sender_name": "Bob",
                "chat_id": 123,
                "chat_title": "Test Chat",
                "is_from_me": False,
                "media": {"type": "photo", "description": "A nice landscape"},
            },
        ),
    ]

    nodes = transform_telegram_docs_to_nodes(docs)

    assert len(nodes) == 2
    assert nodes[0].metadata["author"] == "Alice"
    assert nodes[1].metadata["author"] == "Bob"
    assert json.loads(nodes[1].metadata["media"])["type"] == "photo"
    assert "PREVIOUS MESSAGES" in nodes[1].text

    print("Test passed!")


if __name__ == "__main__":
    test_refactor()
