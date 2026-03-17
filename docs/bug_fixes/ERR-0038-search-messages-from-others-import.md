# ERR-0038: ImportError for search_messages_from_others

## Symptoms
The backend API returns 500 when calling the `search_from_person` tool. The logs show:
`ImportError: cannot import name 'search_messages_from_others' from 'etl.db.chats' (/app/etl/db/chats.py)`

## Investigation Notes
- The error occurs in `backend/retrieval.py`.
- The functions `search_messages_from_others` and `get_recent_messages` were imported from `etl.db.chats`.
- Since the database module refactoring (to `etl/db/`), these functions are actually located in `etl.db.raw_documents` and exported correctly.

## Hypotheses Considered
1. The functions were deleted. (Rejected, found in `etl.db.raw_documents`).
2. The import path in `backend/retrieval.py` was not updated after the `etl.db` refactoring. (Confirmed).

## Experiments Tried
- Checked where `search_messages_from_others` is defined (`etl/db/raw_documents.py`).

## Final Fix
- Updated `backend/retrieval.py` to import `search_messages_from_others`, `get_recent_messages`, and `_escape_like` from `etl.db.raw_documents` instead of `etl.db.chats` and `etl.db.core`.
- Updated `backend/retrieval.py` and `backend/session_tools.py` to import `row_to_raw_document` from `etl.db.core` instead of `_row_to_raw_document`.
- Fixed the `session_helpers` import in `backend/session_tools.py` to `backend.session_helpers`.

## Verification
- Verified by checking imports and running syntax checks with `pytest`.
- Searched codebase to ensure no other incorrect imports from `etl.db.chats`.

## Status
resolved
