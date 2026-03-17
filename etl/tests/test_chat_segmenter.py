"""Unit tests for chat segmentation logic."""
from datetime import datetime, timedelta, timezone

import pytest

from etl.chat_analysis.models import RawMessage
from etl.chat_analysis.segmenter import (
    build_chat_segments,
    format_message_for_llm,
    select_high_signal_messages,
)
from etl.chat_analysis.token_budget import BudgetConfig, TokenBudget


@pytest.fixture
def test_budget():
    # A tiny budget to easily trigger token splits in tests
    config = BudgetConfig(max_context_tokens=100, output_tokens=0, safety_margin=0)
    return TokenBudget(config)


def make_msg(i: int, minutes_offset: int, content: str = "Hello") -> RawMessage:
    return RawMessage(
        doc_id=f"doc_{i}",
        chat_id=1,
        source_id=f"doc_{i}",
        sender_id=2,
        sender_name="Alice",
        timestamp=datetime.now(timezone.utc) + timedelta(minutes=minutes_offset),
        content=content,
        metadata={},
    )


def test_format_message_for_llm():
    msg = make_msg(1, 0, "Test message")
    formatted = format_message_for_llm(msg)
    assert "Alice: Test message" in formatted
    assert formatted.startswith("[")


def test_build_chat_segments_empty():
    segments = build_chat_segments(
        chat_id=1, messages=[], budget=TokenBudget()
    )
    assert segments == []


def test_build_chat_segments_time_gap(test_budget):
    # min_msgs = 2, so the gap is respected after 2 messages
    msgs = [
        make_msg(1, 0),
        make_msg(2, 5),
        make_msg(3, 60 * 24),  # 24 hours later -> forces split
        make_msg(4, 60 * 24 + 5),
    ]

    segments = build_chat_segments(
        chat_id=1,
        messages=msgs,
        budget=test_budget,
        time_gap_hours=18,
        min_msgs=2,
    )
    assert len(segments) == 2
    assert segments[0].message_count == 2
    assert segments[1].message_count == 2
    assert segments[0].strategy == "time_gap"
    assert segments[1].strategy == "final"


def test_build_chat_segments_max_msgs(test_budget):
    msgs = [make_msg(i, i) for i in range(10)]
    
    segments = build_chat_segments(
        chat_id=1,
        messages=msgs,
        budget=test_budget,
        max_msgs=4,
        min_msgs=2,
    )
    # Should split: 4 -> 4 -> 2
    assert len(segments) == 3
    assert segments[0].message_count == 4
    assert segments[1].message_count == 4
    assert segments[2].message_count == 2
    assert segments[0].strategy == "max_msgs"


def test_select_high_signal_messages():
    msgs = [
        make_msg(1, 1, "hello there"),
        make_msg(2, 2, "check this link http://example.com"),
        make_msg(3, 3, "yeah me too"),
        make_msg(4, 4, "let's meet at 14:00"),
        make_msg(5, 5, "[PHOTO] nice"),
    ]
    
    top = select_high_signal_messages(msgs, max_messages=3)
    assert len(top) == 3
    
    # Expect the ones with link (3 pts), time (2 pts), photo (2 pts)
    extracted_text = " ".join(m.content for m in top)
    assert "http://" in extracted_text
    assert "14:00" in extracted_text
    assert "[PHOTO]" in extracted_text
    # "hello there" and "yeah me too" should be filtered out
    assert "hello there" not in extracted_text
