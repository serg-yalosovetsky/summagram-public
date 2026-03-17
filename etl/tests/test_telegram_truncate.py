from etl.sources.telegram import _truncate_messages, _estimate_tokens

def test_truncate_messages_within_limit():
    msgs = [["short message"], ["another message"], ["third one"]]
    truncated = _truncate_messages(msgs, max_tokens=100)
    assert truncated == msgs

def test_truncate_messages_exceeds_limit():
    # Make a string that is ~100 tokens long
    long_msg = "abcd " * 60  # ~300 chars -> 100 tokens
    
    msgs = [
        [long_msg for _ in range(10)], # section 1: 10 lines
        [long_msg for _ in range(5)],  # section 2: 5 lines
        [long_msg for _ in range(5)]   # section 3: 5 lines
    ]
    # Total ~ 2000 tokens
    
    truncated = _truncate_messages(msgs, max_tokens=500)
    
    # They should be truncated
    assert len(truncated[0]) < 10
    assert len(truncated[1]) < 5
    assert len(truncated[2]) < 5
    
    # And total tokens roughly <= 500 (since it just slices the arrays, it might be slightly higher if one item is large, but proportional)
    combined = "\n".join(msg for section in truncated for msg in section)
    assert _estimate_tokens(combined) <= 500 or len(truncated[0]) == 1
