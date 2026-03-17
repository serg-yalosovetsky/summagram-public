from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.table import Table

ID = "2026-03-06T01:22:32:579542"
VERSION = "1.32.0"
DESCRIPTION = "custom_indices"

class RawTable(Table):
    """
    Dummy table for executing raw SQL via Piccolo.
    """
    pass

APP_NAME = "etl"

async def forwards():
    manager = MigrationManager(
        migration_id=ID,
        app_name=APP_NAME,
        description=DESCRIPTION,
    )

    async def run():
        statements = [
            # ---------------------------------------------------------
            # Preflight: duplicates for UNIQUE on unified_events
            # ---------------------------------------------------------
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM unified_events
                    GROUP BY source_id, evidence_msg_id
                    HAVING COUNT(*) > 1
                ) THEN
                    RAISE EXCEPTION
                        'Cannot add uq_unified_events_source_evidence: duplicates exist in unified_events(source_id, evidence_msg_id)';
                END IF;
            END
            $$;
            """,
            # ---------------------------------------------------------
            # Preflight: duplicates for UNIQUE on raw_documents
            # ---------------------------------------------------------
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM raw_documents
                    GROUP BY source_id, doc_id
                    HAVING COUNT(*) > 1
                ) THEN
                    RAISE EXCEPTION
                        'Cannot add uq_raw_docs_source_doc: duplicates exist in raw_documents(source_id, doc_id)';
                END IF;
            END
            $$;
            """,
            # ---------------------------------------------------------
            # Preflight: duplicates for UNIQUE on indexed_documents
            # ---------------------------------------------------------
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM indexed_documents
                    GROUP BY source_id, doc_id
                    HAVING COUNT(*) > 1
                ) THEN
                    RAISE EXCEPTION
                        'Cannot add uq_idx_docs_source_doc: duplicates exist in indexed_documents(source_id, doc_id)';
                END IF;
            END
            $$;
            """,
            # ---------------------------------------------------------
            # Preflight: nulls / duplicates for UNIQUE on chat_members
            # ---------------------------------------------------------
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM chat_members
                    WHERE chat_id IS NULL OR user_id IS NULL
                ) THEN
                    RAISE EXCEPTION
                        'Cannot add uq_chat_members_chat_user: NULL values exist in chat_members(chat_id, user_id)';
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM chat_members
                    GROUP BY chat_id, user_id
                    HAVING COUNT(*) > 1
                ) THEN
                    RAISE EXCEPTION
                        'Cannot add uq_chat_members_chat_user: duplicates exist in chat_members(chat_id, user_id)';
                END IF;
            END
            $$;
            """,
            # ---------------------------------------------------------
            # Guarded constraints
            # ---------------------------------------------------------
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_unified_events_source_evidence'
                      AND conrelid = 'unified_events'::regclass
                ) THEN
                    ALTER TABLE unified_events
                    ADD CONSTRAINT uq_unified_events_source_evidence
                    UNIQUE (source_id, evidence_msg_id);
                END IF;
            END
            $$;
            """,
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_raw_docs_source_doc'
                      AND conrelid = 'raw_documents'::regclass
                ) THEN
                    ALTER TABLE raw_documents
                    ADD CONSTRAINT uq_raw_docs_source_doc
                    UNIQUE (source_id, doc_id);
                END IF;
            END
            $$;
            """,
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_idx_docs_source_doc'
                      AND conrelid = 'indexed_documents'::regclass
                ) THEN
                    ALTER TABLE indexed_documents
                    ADD CONSTRAINT uq_idx_docs_source_doc
                    UNIQUE (source_id, doc_id);
                END IF;
            END
            $$;
            """,
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_chat_members_chat_user'
                      AND conrelid = 'chat_members'::regclass
                ) THEN
                    ALTER TABLE chat_members
                    ADD CONSTRAINT uq_chat_members_chat_user
                    UNIQUE (chat_id, user_id);
                END IF;
            END
            $$;
            """,
            # ---------------------------------------------------------
            # Indexes
            # ---------------------------------------------------------
            # Safer partial index: only rows with numeric chat_id are indexed.
            """
            CREATE INDEX IF NOT EXISTS idx_raw_docs_chat_id
            ON raw_documents (((metadata->>'chat_id')::bigint))
            WHERE metadata ? 'chat_id'
              AND (metadata->>'chat_id') ~ '^-?[0-9]+$';
            """,
            # Safer partial index: only rows with boolean-like values are indexed.
            """
            CREATE INDEX IF NOT EXISTS idx_raw_docs_is_from_me
            ON raw_documents (((metadata->>'is_from_me')::boolean))
            WHERE metadata ? 'is_from_me'
              AND lower(metadata->>'is_from_me') IN (
                  'true', 'false',
                  't', 'f',
                  'yes', 'no',
                  'y', 'n',
                  'on', 'off',
                  '1', '0'
              );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_raw_docs_session_id
            ON raw_documents ((metadata->>'session_id'))
            WHERE metadata ? 'session_id';
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_raw_docs_timestamp
            ON raw_documents (timestamp);
            """
        ]

        for sql in statements:
            await RawTable.raw(sql)

    manager.add_raw(run)

    async def run_backwards():
        statements = [
            # ---------------------------------------------------------
            # Drop indexes first
            # ---------------------------------------------------------
            "DROP INDEX IF EXISTS idx_raw_docs_timestamp;",
            "DROP INDEX IF EXISTS idx_raw_docs_session_id;",
            "DROP INDEX IF EXISTS idx_raw_docs_is_from_me;",
            "DROP INDEX IF EXISTS idx_raw_docs_chat_id;",
            # ---------------------------------------------------------
            # Drop constraints (guarded)
            # ---------------------------------------------------------
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_chat_members_chat_user'
                      AND conrelid = 'chat_members'::regclass
                ) THEN
                    ALTER TABLE chat_members
                    DROP CONSTRAINT uq_chat_members_chat_user;
                END IF;
            END
            $$;
            """,
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_idx_docs_source_doc'
                      AND conrelid = 'indexed_documents'::regclass
                ) THEN
                    ALTER TABLE indexed_documents
                    DROP CONSTRAINT uq_idx_docs_source_doc;
                END IF;
            END
            $$;
            """,
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_raw_docs_source_doc'
                      AND conrelid = 'raw_documents'::regclass
                ) THEN
                    ALTER TABLE raw_documents
                    DROP CONSTRAINT uq_raw_docs_source_doc;
                END IF;
            END
            $$;
            """,
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_unified_events_source_evidence'
                      AND conrelid = 'unified_events'::regclass
                ) THEN
                    ALTER TABLE unified_events
                    DROP CONSTRAINT uq_unified_events_source_evidence;
                END IF;
            END
            $$;
            """,
        ]

        for sql in statements:
            await RawTable.raw(sql)

    manager.add_raw_backwards(run_backwards)

    return manager
