# User Stories & System Interactions

This document describes the primary interactions with Summagram from both the end-user perspective and the internal system/developer perspective.

## 1. Initial Setup & Telegram Sync

### User Perspective
- **Goal**: Ingest my Telegram chat history to make it searchable and extract life events.
- **Interaction**:
    1. Navigate to the **Datasets** view in the Next.js app.
    2. Click **Reprocess All Media** (or use the Sources settings if implemented).
    3. Observe the **ETL Progress Footer** slide up from the bottom.
    4. Track real-time progress (e.g., "Indexing 20 documents...") until it reaches 100%.
    5. The footer disappears automatically once the sync is verified.

### Developer Perspective (Behind the Scenes)
1. **Load Chats**:
    - `Frontend` sends a `GET` request to `ETL Service` (`/sources/telegram/dialogs`).
    - `ETL Service` connects to `Telethon` (using the mounted session) and returns a list of dialogs.
    - `Frontend` saves these in its session state and renders checkboxes.
2. **Submit Job**:
    - `Frontend` sends a `POST` request to `ETL Service` (`/jobs/telegram`) with `chat_ids` and `days_back`.
    - `ETL Service` generates a `job_id`, queues the task, and returns the ID immediately.
3. **Job Execution (Async in ETL)**:
    - `ETL` fetches messages from Telegram.
    - **Media Support**: If a message has an image, `ETL` downloads it to `./storage/media` and calls `Backend` (`/analyze-image`).
    - **Data Persistence**: `ETL` saves normalized messages to `summagram.db` (`raw_documents` table).
    - **Indexing**: `ETL` transforms documents to `TextNode` (including media context) and inserts them into `ChromaDB`.
4. **Real-time Progress Tracking**:
    - `Frontend` (`AppContext`) detects an `activeJobId`.
    - An interval is started to call `ETL Service` (`/jobs/{id}`) every 1.5s.
    - `EtlFooter` displays the `message` (activity) and `progress` from the ETL job state.
    - Once `status` is `completed`, the footer shows "Sync Completed" and self-destructs after 3s.

---

## 2. Global Chat & Assistant

### User Perspective
- **Goal**: Ask questions about my history, find specific info, or get a summary.
- **Interaction**:
    1. Navigate to the **Chat** tab.
    2. Type a question (e.g., "What was my last message?", "Who do I owe money to?").
    3. View the assistant's response, which streams in real-time.

### Developer Perspective (Behind the Scenes)
1. **Recent History Retrieval**:
    - `Frontend` queries the local SQLite `summagram.db` for the last 10 raw messages.
    - **Media Awareness**: The query includes `metadata` to parse and include media descriptions in the "recent" context.
2. **Semantic Search (RAG)**:
    - `Frontend` (via LlamaIndex) calls `Backend` (`/v1/embeddings`) to vectorize the user query.
    - `Frontend` queries `ChromaDB` for the most relevant nodes (top-K).
3. **Prompt Construction**:
    - `Frontend` combines the retrieved context, the recent history, and the user query into a system prompt.
4. **Inference**:
    - `Frontend` sends the final prompt to `Backend` (`/v1/chat/completions`) with `stream=True`.
    - `Backend` (vLLM) generates the response chunk by chunk.
    - `Frontend` renders the stream in the Markdown-capable chat interface.

---

## 3. Reviewing Extracted Events

### User Perspective
- **Goal**: See a structured overview of my life (debts, interviews, top-ups).
- **Interaction**:
    1. Navigate to the **Dashboard** tab.
    2. View metrics (Total Events, Indexed Messages).
    3. Scroll through the **Upcoming Events** table to see structured data extracted from chats.

### Developer Perspective (Behind the Scenes)
1. **Metrics**:
    - `Frontend` calls Backend `/chats` and `/documents` to calculate summary statistics.
2. **Event Listing**:
    - `Frontend` queries the `unified_events` table via Backend.
3. **Social Graph**:
    - User clicks the **Network** tab.
    - `Frontend` calls ETL `/graph/data`.
    - `Frontend` renders the interactive force-graph using `react-force-graph-2d`.
    - User can click nodes/users to see their latest messages and interest tags.

---

## 4. Debugging & Datasets

### User Perspective
- **Goal**: Verify what data has actually been ingested and trigger reprocessing.
- **Interaction**:
    1. Navigate to the **Datasets** tab.
    2. View the list of **Raw Documents** (ID, Source, and snippet of content).
    3. Click **Reprocess All Media** to update analysis for existing files.
    4. Observe the **ETL Progress Footer** for real-time feedback.

### Developer Perspective (Behind the Scenes)
1. **Listing Documents**:
    - `Frontend` queries the `raw_documents` table via Backend `/documents` endpoint.
2. **Reprocessing**:
    - `Frontend` calls `ETL Service` `/reindex-media`.
    - `ETL Service` iterates through DB, identifies media files, and re-runs the analysis pipeline.
    - Progress is reported back via the job polling system described in Story 1.
