"""
Chat segmenter: cuts a sorted message list into LLM-ready windows.

Segmentation strategy (in priority order):
  1. Time gap > TIME_GAP_HOURS → forced break (if segment has >= min_msgs)
  2. Estimated token count > max_input_tokens → forced break (if >= min_msgs)
  3. Message count > max_msgs → forced break
  4. Flush remainder as 'final' segment
"""
from __future__ import annotations

from datetime import datetime, timedelta

from etl.chat_analysis.models import ChatSegment, RawMessage
from etl.chat_analysis.token_budget import TokenBudget


MAX_MSGS_PER_SEGMENT: int = 40
MAX_INPUT_TOKENS_PER_SEGMENT: int = 2200
TIME_GAP_HOURS: int = 18
MIN_MSGS_PER_SEGMENT: int = 8


def format_message_for_llm(msg: RawMessage) -> str:
    """Format a single message for LLM consumption.

    Output format: [ISO_TIMESTAMP] sender_name: content
    Media markers embedded in `content` (e.g. [PHOTO] ...) are preserved as-is.
    """
    text = (msg.content or "").strip()
    if not text:
        text = "[EMPTY MESSAGE]"
    return f"[{msg.timestamp.isoformat()}] {msg.sender_name}: {text}"


def _join_messages(messages: list[RawMessage]) -> str:
    return "\n".join(format_message_for_llm(m) for m in messages)


def build_chat_segments(
    *,
    chat_id: int,
    messages: list[RawMessage],
    budget: TokenBudget,
    max_msgs: int = MAX_MSGS_PER_SEGMENT,
    max_input_tokens: int = MAX_INPUT_TOKENS_PER_SEGMENT,
    time_gap_hours: int = TIME_GAP_HOURS,
    min_msgs: int = MIN_MSGS_PER_SEGMENT,
) -> list[ChatSegment]:
    """
    Split a time-sorted message list into LLM-friendly segments.

    Args:
        chat_id: DB chat identifier.
        messages: Messages sorted ascending by timestamp.
        budget: TokenBudget for estimating segment sizes.
        max_msgs: Hard cap on messages per segment.
        max_input_tokens: Token ceiling for a single segment's text.
        time_gap_hours: Hours of silence that trigger a new segment.
        min_msgs: Minimum messages before a gap/budget split is applied.

    Returns:
        List of ChatSegment dataclasses, ready to persist and feed to LLM.
    """
    if not messages:
        return []

    segments: list[ChatSegment] = []
    current: list[RawMessage] = []
    segment_no: int = 1
    time_gap = timedelta(hours=time_gap_hours)

    def _flush(strategy: str) -> None:
        nonlocal current, segment_no
        if not current:
            return
        text = _join_messages(current)
        token_estimate = budget.count_text_tokens(text)
        seg = ChatSegment(
            segment_id=f"{chat_id}:{segment_no}",
            chat_id=chat_id,
            segment_no=segment_no,
            start_doc_id=current[0].doc_id,
            end_doc_id=current[-1].doc_id,
            start_ts=current[0].timestamp,
            end_ts=current[-1].timestamp,
            message_count=len(current),
            token_count_estimate=token_estimate,
            strategy=strategy,
            messages=current[:],
            text_for_llm=text,
        )
        segments.append(seg)
        segment_no += 1
        current = []

    for msg in messages:
        if not current:
            current.append(msg)
            continue

        prev = current[-1]
        has_min = len(current) >= min_msgs

        # 1. Time gap
        if has_min and (msg.timestamp - prev.timestamp) > time_gap:
            _flush("time_gap")
            current.append(msg)
            continue

        # 2. Token budget (evaluate adding this message)
        candidate_text = _join_messages(current + [msg])
        candidate_tokens = budget.count_text_tokens(candidate_text)
        if has_min and candidate_tokens > max_input_tokens:
            _flush("token_budget")
            current.append(msg)
            continue

        # 3. Message count cap
        if len(current) >= max_msgs:
            _flush("max_msgs")
            current.append(msg)
            continue

        current.append(msg)

    _flush("final")
    return segments


def select_high_signal_messages(
    messages: list[RawMessage],
    *,
    max_messages: int = 60,
) -> list[RawMessage]:
    """
    Score and select the most signal-rich messages from a large chat.

    Useful when a chat has thousands of messages and a full segmentation
    would be too expensive. Scores by link presence, time/date patterns,
    media markers, and message length.

    Returns:
        Sorted-by-timestamp subset of up to *max_messages* high-signal messages.
    """
    scored: list[tuple[int, RawMessage]] = []

    for msg in messages:
        text = (msg.content or "").lower()
        score = 0

        if "http://" in text or "https://" in text:
            score += 3
        if "zoom" in text or "meet.google" in text or "teams.microsoft" in text:
            score += 3
        # CIS weekday / time hints
        if any(
            x in text
            for x in [
                "вт ", "ср ", "чт ", "пт ", "сб ", "нд ",
                "понед", "tuesday", "wednesday", "thursday",
                ":30", ":00", "14:00", "19:00",
            ]
        ):
            score += 2
        if any(
            marker in text
            for marker in ["[photo]", "[audio transcript]", "[document]", "[voice]"]
        ):
            score += 2
        if len(text) > 200:
            score += 1

        if score > 0:
            scored.append((score, msg))

    scored.sort(key=lambda item: (-item[0], item[1].timestamp))
    top = [msg for _, msg in scored[:max_messages]]
    top.sort(key=lambda m: m.timestamp)
    return top
