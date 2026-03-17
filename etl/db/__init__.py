"""
etl.db — Database access layer (asyncpg, native PostgreSQL).

Backward-compatible re-exports: code that did
    from etl.database import get_chat
will keep working after database.py is replaced.
"""

from etl.db.core import (  # noqa: F401
    DatabasePoolManager,
    db_manager,
    get_db,
    init_db,
    row_to_raw_document,
    row_to_session,
    transaction,
)
from etl.db.raw_documents import (  # noqa: F401
    add_downloaded_range,
    get_all_documents,
    get_chat_history,
    get_document_counts_by_type,
    get_downloaded_ranges,
    get_indexed_status,
    get_last_message_any_chat,
    get_last_messages_any_chat,
    get_raw_documents_by_ids,
    get_recent_messages,
    get_recent_messages_from_others,
    get_recent_raw_messages,
    get_surrounding_messages,
    mark_as_indexed,
    save_message,
    save_raw_documents,
    search_documents_by_media,
    search_messages_from_others,
    update_raw_document,
)
from etl.db.chats import (  # noqa: F401
    build_multilingual_prefix_patterns,
    find_chats_by_contact_name,
    get_chat,
    get_chat_message_stats,
    get_chats,
    get_contact,
    get_contacts,
    get_latest_graph_cache,
    get_reply_interaction_freq,
    save_chat,
    save_chat_member,
    save_contact,
    save_graph_cache,
)
from etl.db.sessions import (  # noqa: F401
    create_session,
    get_session,
    get_session_messages,
    get_sessions,
    insert_session_message,
    update_session_title,
    update_session_updated_at,
)
from etl.db.chat_analysis import ( # noqa: F401
    get_raw_docs_for_chat,
    get_chat_members_with_contacts,
    replace_chat_segments,
    save_segment_analysis,
    upsert_unified_events,
)



# Backward-compatible aliases for internal helpers used by backend/retrieval.py & session_tools.py
_row_to_raw_document = row_to_raw_document
def _parse_metadata(val):
    return __import__("etl.db.core", fromlist=["_parse_jsonish"])._parse_jsonish(val)

from etl.db.raw_documents import _escape_like  # noqa: F401, E402
