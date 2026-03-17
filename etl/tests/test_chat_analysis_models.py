"""Unit tests for chat analysis models and token budget."""
import pytest
from pydantic import ValidationError

from etl.chat_analysis.models import ChatSegmentAnalysis
from etl.chat_analysis.token_budget import TokenBudget


def test_token_budget_text():
    budget = TokenBudget()
    text = "Hello world this is a test"
    # Length is 26. 26 / 2.5 = 10.4 -> 10
    assert budget.count_text_tokens(text) == 10
    
    # Very short text should be 1
    assert budget.count_text_tokens("hi") == 1


def test_token_budget_chat():
    budget = TokenBudget()
    messages = [
        {"role": "user", "content": "Hello!"} # 6 len -> 2 tokens + 8 overhead = 10
    ]
    # Total: 10 + 3 generation overhead = 13
    assert budget.count_chat_tokens(messages) == 13

    
def test_pydantic_roundtrip():
    data = {
        "segment_id": "123:1",
        "summary": "A test segment",
        "topics": [{"label": "test", "kind": "topic", "confidence": 0.9, "evidence_quotes": []}],
        "people": [{"display_name": "Alice", "role": "friend", "confidence": 0.8}],
        "interests": [],
        "events": [
            {
                "title": "Meeting",
                "event_type": "meeting",
                "confidence": 0.7,
                "participants": ["Alice"]
            }
        ],
        "places": ["Kyiv"],
        "relationship_signals": [],
        "emotional_tone": ["happy"],
        "importance_score": 0.5,
        "confidence": 0.8
    }
    
    obj = ChatSegmentAnalysis.model_validate(data)
    assert obj.summary == "A test segment"
    assert len(obj.topics) == 1
    assert obj.topics[0].label == "test"
    
    dumped = obj.model_dump(mode="json")
    assert dumped["segment_id"] == "123:1"
    
    # Bad role validation
    with pytest.raises(ValidationError):
        data["people"][0]["role"] = "invalid_role"
        ChatSegmentAnalysis.model_validate(data)
