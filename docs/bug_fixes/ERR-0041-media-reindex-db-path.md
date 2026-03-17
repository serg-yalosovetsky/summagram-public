# ERR-0041: Media Reindex DB Path Error

## Symptoms
`etl-1` container logs showed an error when trying to run tests/jobs:
`AttributeError: type object 'Config' has no attribute 'DB_PATH'`
This error occurred in `/app/etl/sources/media_reindex_source.py` around line 34, because `SQLiteRepository` was expecting `Config.DB_PATH` which was removed during the recent database refactoring out of SQLite.

## Investigation Notes
- Examined `media_reindex_source.py` and traced code path to `SQLiteRepository`.
- Project has transitioned completely to PostgreSQL and Piccolo ORM, effectively deprecating `SQLiteRepository` and config entries like `DB_PATH`.
- Found that `SQLiteRepository` is only imported by `media_reindex_source.py` and `repositories.py`.

## Final Fix
- Moved the `fetch_documents_for_reindex` async SQL fetch logic inside `/app/etl/db/raw_documents.py`. Used asyncpg raw cursor along with existing `row_to_raw_document` parser, similar to other helper methods in that module.
- Refactored `MediaReindexSource` to call the new `fetch_documents_for_reindex` query, treating rows as `RawDocumentRow` Pydantic objects instead of parsing raw JSON.
- Removed dead SQLite usage from source.

## Verification
- Can run ETL unit tests (they will be run after the fix to verify everything works properly).

## Status
Resolved
