# Database Schema

This document outlines the database schema for the Summagram application. The application uses **PostgreSQL** for data persistence, accessed via `asyncpg`, with **Piccolo ORM** managing schema definitions and migrations (`etl/tables.py` and `etl/migrations/`).

## Tables

### `unified_events`
Stores extracted events from various sources.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | Unique identifier for the event. |
| `event_type` | TEXT NOT NULL | Type of event (e.g., 'debt', 'interview', 'topup'). |
| `start_time` | TEXT NOT NULL | ISO8601 formatted start time. |
| `end_time` | TEXT NOT NULL | ISO8601 formatted end time. |
| `title` | TEXT NOT NULL | Concise title of the event. |
| `payload` | JSONB | JSON object containing event-specific details. |
| `evidence_msg_id` | TEXT | ID of the source message that evidenced this event. |
| `source_id` | TEXT | ID of the source (e.g., chat ID or channel ID). |
| `calendar_sync_status` | INTEGER DEFAULT 0 | Status of synchronization with external calendars. |
| `created_at` | TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP | Record creation timestamp. |

**Constraints:**
- `UNIQUE(source_id, evidence_msg_id)`: Prevents duplicate events from the same message.

### `sync_states`
Tracks the synchronization progress for each data source.

| Column | Type | Description |
| :--- | :--- | :--- |
| `source_id` | TEXT PRIMARY KEY | Unique identifier for the data source. |
| `last_synced_at` | TIMESTAMPTZ | Timestamp of the last successful sync. |
| `last_msg_id` | INTEGER | ID of the last processed message. |
| `meta` | JSONB | Additional metadata for the sync state. |

### `raw_documents`
Stores raw content ingested from sources before processing.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | Unique identifier. |
| `source_id` | TEXT | ID of the source. |
| `doc_id` | TEXT | Unique ID of the document within the source. |
| `content` | TEXT | Raw text content of the document. |
| `timestamp` | TIMESTAMPTZ | Timestamp of the document. |
| `metadata` | JSONB | Additional metadata (sender, chat info, and media object). |

**Constraints:**
- `UNIQUE(source_id, doc_id)`: Ensures unique documents per source.

### `download_ranges`
Tracks the time ranges of chat history that have been downloaded.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | Unique identifier. |
| `chat_id` | TEXT NOT NULL | ID of the chat. |
| `start_date` | TIMESTAMPTZ NOT NULL | ISO8601 start date of the range. |
| `end_date` | TIMESTAMPTZ NOT NULL | ISO8601 end date of the range. |
| `created_at` | TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP | Record creation timestamp. |

### `indexed_documents`
Tracks documents that have been indexed (e.g., for vector search).

| Column | Type | Description |
| :--- | :--- | :--- |
| `source_id` | TEXT | ID of the source. |
| `doc_id` | TEXT | ID of the document. |
| `indexed_at` | TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP | Timestamp when the document was indexed. |

**Constraints:**
- `UNIQUE(source_id, doc_id)`: Prevents duplicate index entries.

### `chats`
Stores metadata and importance scores for chats.

| Column | Type | Description |
| :--- | :--- | :--- |
| `source_id` | BIGINT PRIMARY KEY | Telegram chat ID. |
| `title` | TEXT | Chat title. |
| `description` | TEXT | AI-generated chat description. |
| `tags` | JSONB | List of tags (interests). |
| `message_count_total`| INTEGER | Total messages in chat. |
| `message_count_me` | INTEGER | Messages sent by the user. |
| `importance_score` | FLOAT | Computed priority (0.0 - 1.0). |
| `is_private` | BOOLEAN | True for 1-to-1 chats. |
| `last_analyzed_at` | TIMESTAMPTZ | Last analysis timestamp. |

### `contacts`
Stores information about users (contacts).

| Column | Type | Description |
| :--- | :--- | :--- |
| `source_id` | BIGINT PRIMARY KEY | Telegram user ID. |
| `name` | TEXT | Full name. |
| `username` | TEXT | Telegram username. |
| `interests` | JSONB | List of interest clusters. |
| `description` | TEXT | AI-generated bio summary. |

### `chat_members`
Many-to-many relationship between chats and contacts.

### `chat_segments`
Stores non-overlapping logical chunks of chat message history for batch LLM analysis.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | Unique identifier. |
| `chat_id` | BIGINT NOT NULL | Reference to the chat. |
| `segment_no` | INTEGER NOT NULL | Sequential chunk number for the chat. |
| `start_message_doc_id`| TEXT | First message ID in the segment. |
| `end_message_doc_id` | TEXT | Last message ID in the segment. |
| `start_ts` | TEXT | ISO timestamp of the start. |
| `end_ts` | TEXT | ISO timestamp of the end. |
| `message_count`| INTEGER | Number of messages in this segment. |
| `token_count_estimate`| INTEGER | Approximate token count. |
| `strategy` | TEXT | Reason for splitting (e.g. `time_gap`, `max_msgs`, `token_budget`). |
| `text_for_llm`| TEXT | Pre-formatted text payload for LLM processing. |

**Constraints:**
- `UNIQUE(chat_id, segment_no)`: Prevents duplicate segments per chat.

### `chat_segment_analysis`
Stores the structured analytical outputs mapped to a single `chat_segment`.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | Unique identifier. |
| `segment_id` | BIGINT NOT NULL UNIQUE | Reference to `chat_segments.id`. |
| `model_name` | TEXT NOT NULL | LLM model used for inference. |
| `summary` | TEXT | Summary of the segment. |
| `topics` | JSONB | List of topics extracted. |
| `people` | JSONB | List of people identified. |
| `events` | JSONB | List of possible events extracted. |
| `interests` | JSONB | List of interests inferred. |
| `places` | JSONB | Locations mentioned. |
| `relationship_signals`| JSONB | Inferred relationship context. |
| `tone` | JSONB | Emotional tone. |
| `importance_score` | FLOAT | Computed importance for this chunk. |
| `raw_json` | JSONB | Complete JSON output from LLM. |

### `social_graph_cache`
Stores serialized NetworkX graph data for the frontend.

## Data Models (Pydantic)

These models correspond to the data structures used in the application logic.

### Generic
- **`GenericDocument`**: Represents a source-agnostic document with `source_id`, `doc_id`, `content`, `timestamp`, and `metadata`.
- **`SyncState`**: Represents the sync state with `source_id`, `last_synced_at`, `last_msg_id`, and `meta`.

### Telegram Specific
- **`TelegramMetadata`**:
    - `sender_id`, `sender_name`, `chat_id`, `chat_title`, `is_from_me`, `reply_to_msg_id`.
    - **`media`**: `TelegramMediaMetadata` object.
- **`TelegramMediaMetadata`**:
    - `type`, `extension`, `path`, `description`, `size`, `mime`, `duration`, `title`, `performer`, `width`, `height`, `is_meme`, `is_portrait`, `tags`, `url`.

### Events
Base class: **`BaseEvent`** (`title`, `start_time`, `end_time`)

- **`DebtEvent`**: `amount`, `currency`, `debtor`, `direction` ('i_owe'/'they_owe').
- **`InterviewEvent`**: `company_name`, `interviewer_name`, `meeting_link`, `interview_type`.
- **`TopUpEvent`**: `service_name`, `amount_needed`.

### New Backend Models
- **`Chat`**: Corresponds to `chats` table.
- **`Contact`**: Corresponds to `contacts` table.
- **`UserProfile`**: Used for social graph analysis aggregation.

### Chat Analysis Pipeline Data Models
- **`ChatSegment`**: Dataclass holding raw messages mapped to a segment.
- **`ChatSegmentAnalysis`**: Pydantic model for deeply structured outputs covering topics, people, events, relationship_signals, places, emotional tone, and importance score per segment.
- **`ChatAggregateAnalysis`**: Pydantic model containing the final deduplicated roll-up of all segments for a specific chat (used for `description`, `tags`, `dominant_topics`).
- **`ContactAggregateAnalysis`**: Pydantic model representing synthesized bio and interests from a person across all parsed chats.
