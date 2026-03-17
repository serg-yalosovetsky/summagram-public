"""
Tests for build_multilingual_prefix_patterns (cross-script) and find_chats_by_contact_name.
"""

import pytest

pytestmark = pytest.mark.integration


def test_build_multilingual_prefix_patterns_latin_returns_cyrillic():
    """Latin query produces Cyrillic prefix variants for matching."""
    from etl.db.chats import build_multilingual_prefix_patterns

    prefixes = build_multilingual_prefix_patterns("lev")
    assert "lev%" in prefixes
    assert "лев%" in prefixes


def test_build_multilingual_prefix_patterns_cyrillic_returns_latin():
    """Cyrillic query produces Latin prefix variant."""
    from etl.db.chats import build_multilingual_prefix_patterns

    prefixes = build_multilingual_prefix_patterns("лев")
    assert "лев%" in prefixes
    assert "lev%" in prefixes


def test_build_multilingual_prefix_patterns_russian_ukrainian_alisa():
    """Russian and Ukrainian spellings both produce matching prefix variants."""
    from etl.db.chats import build_multilingual_prefix_patterns

    # User types Russian "Алиса" -> prefixes from first 4 chars of each variant
    prefixes_ru = build_multilingual_prefix_patterns("Алиса")
    assert "алис%" in prefixes_ru
    assert "alis%" in prefixes_ru
    # User types Ukrainian "Аліса"
    prefixes_uk = build_multilingual_prefix_patterns("Аліса")
    assert "аліс%" in prefixes_uk or "алис%" in prefixes_uk
    assert "alis%" in prefixes_uk


def test_build_multilingual_prefix_patterns_empty():
    from etl.db.chats import build_multilingual_prefix_patterns

    assert build_multilingual_prefix_patterns("") == []
    assert build_multilingual_prefix_patterns("   ") == []


def test_build_multilingual_prefix_patterns_short_name():
    """Short names (<=4 chars) use full string as prefix."""
    from etl.db.chats import build_multilingual_prefix_patterns

    prefixes = build_multilingual_prefix_patterns("Ян")
    assert "ян%" in prefixes


@pytest.mark.asyncio
async def test_find_chats_by_contact_name_match_by_contact_name(db_init):
    """find_chats_by_contact_name returns chat when contact name matches (Latin)."""
    from etl.db.chats import (
        save_chat,
        save_contact,
        save_chat_member,
        find_chats_by_contact_name,
    )

    await save_chat({"source_id": 1001, "title": "Lev"})
    await save_contact({"source_id": 2001, "name": "Lev", "username": "lev_u"})
    await save_chat_member(1001, 2001)
    results = await find_chats_by_contact_name("lev")
    assert len(results) >= 1
    by_id = {r.chat_id: r for r in results}
    assert 1001 in by_id
    assert by_id[1001].contact_name == "Lev"
    assert by_id[1001].chat_title == "Lev"


@pytest.mark.asyncio
async def test_find_chats_by_contact_name_match_cyrillic(db_init):
    """find_chats_by_contact_name finds contact stored as Cyrillic when query is Latin."""
    from etl.db.chats import (
        save_chat,
        save_contact,
        save_chat_member,
        find_chats_by_contact_name,
    )

    await save_chat({"source_id": 1002, "title": "Лев"})
    await save_contact({"source_id": 2002, "name": "Лев", "username": None})
    await save_chat_member(1002, 2002)
    results = await find_chats_by_contact_name("lev")
    assert len(results) >= 1
    chat_ids = [r.chat_id for r in results]
    assert 1002 in chat_ids


@pytest.mark.asyncio
async def test_find_chats_by_contact_name_nominative_ukrainian_contact(db_init):
    """find_chats_by_contact_name finds contact 'Аліса' when query is nominative 'Аліса' or 'Алиса'."""
    from etl.db.chats import (
        save_chat,
        save_contact,
        save_chat_member,
        find_chats_by_contact_name,
    )

    await save_chat({"source_id": 1005, "title": "Аліса"})
    await save_contact({"source_id": 2005, "name": "Аліса", "username": None})
    await save_chat_member(1005, 2005)
    for query in ("Аліса", "Алиса", "alisa"):
        results = await find_chats_by_contact_name(query, limit=10)
        assert len(results) >= 1, f"Query {query!r} should find Аліса"
        by_id = {r.chat_id: r for r in results}
        assert 1005 in by_id
        assert by_id[1005].contact_name == "Аліса"


@pytest.mark.asyncio
async def test_find_chats_by_contact_name_nominative_lev(db_init):
    """find_chats_by_contact_name finds contact 'Лев' when query is nominative 'Лев' or 'lev'."""
    from etl.db.chats import (
        save_chat,
        save_contact,
        save_chat_member,
        find_chats_by_contact_name,
    )

    await save_chat({"source_id": 1006, "title": "Лев"})
    await save_contact({"source_id": 2006, "name": "Лев", "username": None})
    await save_chat_member(1006, 2006)
    results = await find_chats_by_contact_name("Лев", limit=10)
    assert len(results) >= 1
    by_id = {r.chat_id: r for r in results}
    assert 1006 in by_id
    assert by_id[1006].contact_name == "Лев"


@pytest.mark.asyncio
async def test_find_chats_by_contact_name_russian_query_ukrainian_contact(db_init):
    """find_chats_by_contact_name finds contact stored as Ukrainian 'Аліса' when query is Russian 'алиса'."""
    from etl.db.chats import (
        save_chat,
        save_contact,
        save_chat_member,
        find_chats_by_contact_name,
    )

    await save_chat({"source_id": 1004, "title": "Аліса"})
    await save_contact({"source_id": 2004, "name": "Аліса", "username": None})
    await save_chat_member(1004, 2004)
    results = await find_chats_by_contact_name("алиса")
    assert len(results) >= 1
    by_id = {r.chat_id: r for r in results}
    assert 1004 in by_id
    assert by_id[1004].contact_name == "Аліса"


@pytest.mark.asyncio
async def test_find_chats_by_contact_name_match_by_chat_title(db_init):
    """find_chats_by_contact_name finds chat when chat title matches (prefix)."""
    from etl.db.chats import (
        save_chat,
        save_contact,
        save_chat_member,
        find_chats_by_contact_name,
    )

    await save_chat({"source_id": 1003, "title": "Alisa"})
    await save_contact({"source_id": 2003, "name": "Alisa", "username": None})
    await save_chat_member(1003, 2003)
    results = await find_chats_by_contact_name("alisa")
    assert len(results) >= 1
    by_id = {r.chat_id: r for r in results}
    assert 1003 in by_id


@pytest.mark.asyncio
async def test_find_chats_by_contact_name_private_first(db_init):
    """When multiple chats match (private and group), private chat is first. Uses prefix match."""
    from etl.db.chats import (
        save_chat,
        save_contact,
        save_chat_member,
        find_chats_by_contact_name,
    )

    await save_contact({"source_id": 3001, "name": "Lev", "username": None})
    await save_chat({"source_id": 5001, "title": "Lev", "is_private": True})
    await save_chat({"source_id": 5002, "title": "Lev Group", "is_private": False})
    await save_chat_member(5001, 3001)
    await save_chat_member(5002, 3001)
    results = await find_chats_by_contact_name("lev")
    assert len(results) >= 2
    by_id = {r.chat_id: r for r in results}
    assert 5001 in by_id and 5002 in by_id
    idx_5001 = next(i for i, r in enumerate(results) if r.chat_id == 5001)
    idx_5002 = next(i for i, r in enumerate(results) if r.chat_id == 5002)
    assert results[idx_5001].is_private is True
    assert results[idx_5002].is_private is False
    assert idx_5001 < idx_5002, "Private chat must appear before group chat"


@pytest.mark.asyncio
async def test_find_chats_by_contact_name_no_match(db_init):
    from etl.db.chats import find_chats_by_contact_name

    results = await find_chats_by_contact_name("NonexistentNameXYZ")
    assert results == []
