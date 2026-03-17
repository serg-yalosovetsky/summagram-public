import pytest
def test_dbg():
    from etl.db.chats import build_multilingual_prefix_patterns
    print(type(build_multilingual_prefix_patterns))
