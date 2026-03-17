BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Ensure metadata / meta are jsonb.
-- If they are already jsonb, these ALTERs are safe no-ops.
ALTER TABLE raw_documents
    ALTER COLUMN metadata TYPE jsonb
    USING CASE
        WHEN metadata IS NULL THEN '{}'::jsonb
        WHEN pg_typeof(metadata)::text = 'jsonb' THEN metadata
        ELSE metadata::jsonb
    END;

ALTER TABLE sessions
    ALTER COLUMN meta TYPE jsonb
    USING CASE
        WHEN meta IS NULL THEN NULL
        WHEN pg_typeof(meta)::text = 'jsonb' THEN meta
        ELSE meta::jsonb
    END;

-- Базовые индексы
CREATE UNIQUE INDEX IF NOT EXISTS raw_documents_source_doc_uidx
    ON raw_documents (source_id, doc_id);

CREATE INDEX IF NOT EXISTS raw_documents_timestamp_idx
    ON raw_documents (timestamp DESC);

CREATE INDEX IF NOT EXISTS indexed_documents_doc_id_idx
    ON indexed_documents (doc_id);

CREATE INDEX IF NOT EXISTS download_ranges_chat_id_start_end_idx
    ON download_ranges (chat_id, start_date, end_date);

CREATE INDEX IF NOT EXISTS sessions_updated_at_idx
    ON sessions (updated_at DESC);

CREATE INDEX IF NOT EXISTS chats_importance_score_idx
    ON chats (importance_score DESC, message_count_me DESC);

CREATE INDEX IF NOT EXISTS contacts_name_idx
    ON contacts (name);

CREATE INDEX IF NOT EXISTS contacts_username_idx
    ON contacts (username);

-- JSONB индексы
CREATE INDEX IF NOT EXISTS raw_documents_metadata_gin_idx
    ON raw_documents
    USING GIN (metadata);

CREATE INDEX IF NOT EXISTS raw_documents_chat_id_idx
    ON raw_documents ((metadata->>'chat_id'));

CREATE INDEX IF NOT EXISTS raw_documents_session_id_idx
    ON raw_documents ((metadata->>'session_id'));

CREATE INDEX IF NOT EXISTS raw_documents_sender_id_idx
    ON raw_documents ((metadata->>'sender_id'));

CREATE INDEX IF NOT EXISTS raw_documents_reply_to_msg_id_idx
    ON raw_documents ((metadata->>'reply_to_msg_id'));

CREATE INDEX IF NOT EXISTS raw_documents_media_type_idx
    ON raw_documents ((metadata->'media'->>'type'));

-- Поиск по content ILIKE '%...%'
CREATE INDEX IF NOT EXISTS raw_documents_content_trgm_idx
    ON raw_documents
    USING GIN (content gin_trgm_ops);

-- Поиск по media.description ILIKE '%...%'
CREATE INDEX IF NOT EXISTS raw_documents_media_description_trgm_idx
    ON raw_documents
    USING GIN ((COALESCE(metadata->'media'->>'description', '')) gin_trgm_ops);

-- Поиск по контактам / чатам через ILIKE prefix%
CREATE INDEX IF NOT EXISTS contacts_name_trgm_idx
    ON contacts
    USING GIN (name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS contacts_username_trgm_idx
    ON contacts
    USING GIN (username gin_trgm_ops);

CREATE INDEX IF NOT EXISTS chats_title_trgm_idx
    ON chats
    USING GIN (title gin_trgm_ops);

COMMIT;
