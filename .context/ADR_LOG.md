# Architecture Decision Records (ADR)

## 001. Modular Ingestion Layer
- **Date**: 2026-01-29
- **Context**: We need to support Telegram now, but WhatsApp and Gmail later.
- **Decision**: Create a `BaseSource` abstract class in `sources/base.py` and implement `TelegramSource` as a plugin. Normalizes everything to `GenericDocument`.
- **Why**: Decouples the extraction logic from the data source.
- **Consequences**: We need to maintain a reliable normalization mapping for every new source.

## 002. Storage Strategy
- **Date**: 2026-01-29
- **Context**: Need to store structured events (different shapes) and vector embeddings locally.
- **Decision**: Use **SQLite** with a `payload` JSON column for the polymorphic event shapes (`unified_events` table).
- **Why**: "Local-First" requirement. Postgres is overkill for a personal assistant. JSON column allows adding `MedicationEvent` without `ALTER TABLE`.
- **Consequences**: SQL queries on specific payload fields require JSON operators (sqlite specific).

## 003. Security & Prompt Injection
- **Date**: 2026-01-29
- **Context**: Processing untrusted user chats is a high security risk.
- **Decision**: Implement **XML Tagging** (`<user_data>`) for prompt injection defense and **PII Masking** (`security.mask_pii`) for UI privacy.
- **Why**: Prevents the LLM from executing malicious instructions embedded in chat messages.
- **Consequences**: Small token overhead for tags.

## 004. LLM Provider
- **Date**: 2026-01-29
- **Context**: User requested OpenRouter support.
- **Decision**: Switch LlamaIndex to use `OpenAILike` class instead of strict `OpenAI`.
- **Why**: The strict class validates model names against a hardcoded list, causing crashes with external models like `google/gemini-2.0-flash-001`.

## 005. Hybrid Search Architecture
- **Date**: 2026-01-29
- **Context**: Users need to ask free-form questions ("what happened last week?") in addition to querying structured events.
- **Decision**: Implement a **Local Vector Store** (LlamaIndex default) alongside the SQLite Event Store.
- **Why**: SQLite is great for structured queries (dates, types), but Vector Search is required for semantic retrieval over unstructured text.
- **Consequences**: Data is duplicated: Sync -> SQLite (Raw) -> Vector Store (Embeddings). Storage usage will increase.

## 006. Local Embeddings & Lazy Loading
- **Date**: 2026-01-29
- **Context**: OpenAI embedding API errors were blocking startup. Startup was also slow due to eager initialization.
- **Decision**: 
    1. Switch to **Local Embeddings** (`HuggingFaceEmbedding`) to remove external dependency for vectorization.
    2. Implement **Lazy Loading** for LLM/Embedding models (only init when needed).
- **Why**: Improves reliability (no API keys for embeddings), privacy, and startup performance.
- **Consequences**: First search/indexing operation has a slight delay while models load into memory. Higher RAM usage.

## 007. Async Chat & UI Enhancements
- **Date**: 2026-01-30
- **Context**: Streamlit's sync nature caused UI freeze during chat generation. Chat window needed better management.
- **Decision**: 
    1. Use `asyncio.to_thread` for blocking LLM calls in `app.py`.
    2. Implement a dedicated **Chat Manager Dialog** for selecting active sync sources.
- **Why**: Keeps the UI responsive. Fixes "Chat Window Closed" annoyance by using a stable selection state.

## 008. Dockerization
- **Date**: 2026-01-30
- **Context**: Deployment consistency and reproducible builds were becoming necessary.
- **Decision**: Containerize the application using `Dockerfile` (Python 3.11-slim) and `docker-compose`.
- **Why**: Ensures the environment (dependencies, system tools) is consistent across dev/prod. Simplifies running auxiliary services like ChromaDB.
- **Consequences**: Local development now requires Docker Desktop.

## 009. Advanced Contextual Retrieval
- **Date**: 2026-01-30
- **Context**: Simple vector search failed on short/chatty messages (e.g., "Yes, I agree").
- **Decision**: 
    1. **Context Windowing**: Enrich message Nodes by prepending previous messages (`processing/telegram_etl.py`).
    2. **ChromaDB**: Switch to a robust dedicated vector store.
    3. **Property Graph**: Implement Graph RAG for relationship discovery.
- **Why**: "Yes" is meaningless without the question it answers. Context Windowing solves this. Graph captures "User X knows User Y".
- **Consequences**: Increased token usage for embeddings (duplication in context).

## 010. OpenTelemetry (Observability)
- **Date**: 2026-01-30
- **Context**: Debugging distributed traces (LlamaIndex -> Chroma -> LLM) was difficult with just print statements.
- **Decision**: Integrate **OpenTelemetry** with `phoenix` or generic OTLP collectors. Instrument LlamaIndex via `openinference-instrumentation-llama-index`.
- **Why**: Provides visibility into RAG pipeline latency, token usage, and retrievals.
- **Consequences**: Requires running an OTLP collector (e.g., Phoenix) to visualize traces.

## 011. UV Package Manager
- **Date**: 2026-01-30
- **Context**: `pip` resolution was slow, especially with heavy ML dependencies.
- **Decision**: Adopt **uv** for dependency management and Docker builds.
- **Why**: Extremely fast resolution and installation. Git-dependencies are handled more gracefully.
- **Consequences**: `requirements.txt` is now generated/managed by `uv` (though standard format). Dockerfile uses `uv pip install`.

## 012. UI Modularization
- **Date**: 2026-02-02
- **Context**: `app.py` was becoming a monolith, making it hard to maintain and causing performance issues with Streamlit re-runs.
- **Decision**: Refactor the UI into a separate `ui/` package with specialized modules (`common`, `dashboard`, `sources`, `chat`, `debug`).
- **Why**: Improves code readability, maintainability, and allows for better state management across different sections of the app.
- **Consequences**: Standardized UI layout and simplified `app.py` as a coordinator.

## 013. Local LLM Inference with vLLM
- **Date**: 2026-02-02
- **Context**: Relying solely on external APIs (Groq, OpenRouter) can be costly and raises privacy concerns for personal data.
- **Decision**: Implement a local inference service using **vLLM** to run models locally on available hardware.
- **Why**: Provides a high-performance, private, and cost-effective alternative to cloud-based LLMs.
- **Consequences**: Requires significant local resources (GPU/RAM). Integrated via a custom `inference.py` service.

## 014. Structured Logging with Loguru
- **Date**: 2026-02-02
- **Context**: Standard `print` statements provide poor visibility and are difficult to filter or search in production logs.
- **Decision**: Replace all `print` calls with `loguru` logger.
- **Why**: Provides rich, structured logging with levels, rotation, and better formatting out of the box.
- **Consequences**: Improved auditability and debugging of background processes (ETL, Sync).

## 015. Telemetry with OpenInference
- **Date**: 2026-02-02
- **Context**: Need standard way to trace complex LlamaIndex RAG pipelines and debug Pydantic validation errors in events.
- **Decision**: Adopt **OpenInference** instrumentation for LlamaIndex.
- **Why**: Specifically designed for LLM applications, providing deep visibility into retrieval, completion, and tool-calling events.
- **Consequences**: Integrated into `telemetry.py`, allowing tracing of both sync and async LLM calls.

## 016. Microservices Refactoring
- **Date**: 2026-02-15
- **Context**: The monolithic Streamlit application suffered from severe performance bottlenecks. Build times were slow due to heavy ML dependencies, and the UI was unresponsive during inference or blocking I/O operations.
- **Decision**: Decompose the system into three isolated services:
    1.  **Backend (FastAPI)**: A dedicated, persistent service hosting heavy ML models (vLLM, Transformers) and exposing a REST API.
    2.  **Frontend (Streamlit)**: A lightweight UI client that communicates with the backend via HTTP.
    3.  **Bot (Telegram)**: An isolated service for messaging I/O (planned).
- **Why**:
    -   **Decoupled Lifecycles**: The heavy backend can stay running while the lightweight frontend is reloaded instantly during development.
    -   **Optimized Builds**: Frontend changes no longer trigger multi-gigabyte ML builds.
    -   **Scalability**: Components can be scaled and deployed independently.
- **Consequences**: Increased infrastructure complexity (docker-compose coordination, shared volumes for models/caches).

## 017. ETL Microservice Extraction
- **Date**: 2026-02-15
- **Context**: The Frontend was handling long-running sync jobs (Telegram fetch -> Index -> Extract), which caused UI blocking and timeouts. It also tightly coupled the UI to specific data sources.
- **Decision**: Extract all data ingestion and processing logic into a dedicated **ETL Service**.
- **Why**: 
    1.  **UI Responsiveness**: The UI now just submits a job and polls for status, never blocking.
    2.  **Extensibility**: Adding new sources (Mail, WhatsApp) doesn't clutter the frontend.
    3.  **Unified Interface**: All sources follow a `BaseSource` and `JobManager` pattern.
- **Consequences**: 
    -   Frontend is now a pure thin client (calls Backend for ML, ETL for Data).
    -   `Telethon` session management moves to the ETL container.

## 018. Media Support and Shared Storage
- **Date**: 2026-02-16
- **Context**: The system skipped media messages (images, audio) and users needed context about attachments in chat history.
- **Decision**: 
    1.  Implement **Shared Media Storage** (`/app/storage/media`) via Docker volumes between ETL and Backend.
    2.  Integrate **Multimodal Analysis** (VLM) for images during ETL ingestion.
    3.  Embed media metadata (descriptions, types) directly into Vector Store Nodes.
- **Why**: Allows the LLM to "see" what was sent in the chat even if there was no accompanying text. Enables search over media content.
- **Consequences**: Increased disk usage for media files. Ingestion time increases due to VLM analysis.

## 019. Media Processing Refactoring with Modern Libraries
- **Date**: 2026-02-16
- **Context**: Initial media processing used basic libraries (standard Whisper, PyPDF2) which were slow and limited in functionality. Need to support more document formats and improve performance.
- **Decision**: 
    1.  **Audio**: Replace standard Whisper with **faster-whisper** (4x faster, VAD, auto language detection)
    2.  **Documents**: Adopt **kreuzberg** for PDF/Office processing (10-50x faster, tables/images extraction, OCR)
    3.  **Images**: Add **LLaVA** via ollama as alternative to SmolVLM2 for better quality
    4.  **Reindexing**: Add UI button and `/reindex-media` endpoint for batch reprocessing
- **Why**: 
    - Faster-whisper provides significant speed improvement without accuracy loss
    - Kreuzberg handles complex documents (tables, images) and multiple Office formats
    - LLaVA offers superior image understanding for complex scenes
    - Reindexing allows applying new models to existing media
- **Consequences**: 
    - Additional dependencies (kreuzberg, ollama, faster-whisper)
    - Ollama service required for LLaVA
    - Increased complexity in media processing pipeline
    - Better extraction quality and performance

## 020. Next.js "v0" Frontend Adoption
- **Date**: 2026-02-17
- **Context**: Streamlit, while great for prototyping, was showing performance and layout limitations for a rich, interactive dashboard.
- **Decision**: Adopt a modern Next.js + shadcn/ui frontend (located in `v0/`).
- **Why**: Provides better responsiveness, component reusability, and access to the rich React ecosystem (e.g., force-graphs).
- **Consequences**: Requires a Node.js runtime and build step. LEGACY: The `frontend/` directory remains for development tools and specialized Streamlit views.

## 021. Social Graph & Interest Analysis
- **Date**: 2026-02-18
- **Context**: Users need to understand their network structure and interest clusters beyond simple search.
- **Decision**: Implement a `GraphAnalyzer` in the ETL service using NetworkX and cosine similarity on user embeddings.
- **Why**: Enables relationship discovery and high-level interest mapping across different chats.
- **Consequences**: New API endpoints and database tables required. Requires embedding all user messages for accurate similarity.

## 022. Repository Layer in ETL
- **Date**: 2026-02-18
- **Context**: Multiple services (Backend, ETL) need to access the same SQLite database with complex queries (parsing JSON, message stats).
- **Decision**: Centralize all database access in `etl/database.py` (and `repositories.py`).
- **Why**: Avoids code duplication and ensures consistent query patterns (especially for JSON extraction).
- **Consequences**: Services depend on the ETL database module.

## 023. Centralized ETL Progress Tracking & Footer UI
- **Date**: 2026-02-21
- **Context**: Long-running ETL tasks (sync, reindexing) need to be monitored by the user without blocking page navigation or requiring the user to stay on the triggering view.
- **Decision**: 
    1. Implement a global **Polling Engine** in the Next.js `AppContext`.
    2. Add a persistent **EtlFooter** component that is fixed to the bottom of the viewport.
    3. Replace mock task simulations with real-time API feedback from the ETL service.
- **Why**: Provides a "headless" processing experience where the user can trigger a task and move on to chat or graph analysis while keeping an eye on the background progress.
- **Consequences**: Continuous API polling (every 1.5s) while a job is active. Global state management for `activeJobId`.

## 024. Tool Call Format: JSON-in-XML for Small Models (superseded by 025)
- **Date**: 2026-02-22
- **Context**: Session chat uses a tool-calling flow (e.g. `get_messages`) with small local 3B models. Python-like syntax inside XML (`<tool_call>get_messages(chat_id=123)</tool_call>`) was unreliable to parse with regex and encouraged models to hallucinate closing tags and fake `<tool_result>`.
- **Decision**: Use **JSON-in-XML** for tool calls: `<tool_call>\n{"name": "get_messages", "arguments": {"chat_id": 123, "limit": 5}}\n</tool_call>`. Parser extracts content between tags and uses `json.loads()` (with brace-counting for nested JSON). System prompt instructs the model to STOP after `</tool_call>` and not generate `<tool_result>`.
- **Why**: Reliable parsing, less ambiguity for small models, and explicit instruction to avoid post-call hallucination.
- **Consequences**: Backend and tests must use the new format; old Python-like format is no longer supported.
- **Superseded by**: ADR 025 (guided JSON).

## 025. Session Tool Calls: Guided JSON (vLLM Structured Outputs)
- **Date**: 2026-02-22
- **Context**: JSON-in-XML (ADR 024) still required regex and brace-counting, with no guaranteed stop and risk of malformed output. Session chat needed a more reliable, token-efficient format for small local models.
- **Decision**: Use **guided JSON** for session agent turns: a single JSON object conforming to Pydantic `AgentResponse` (`thought`, optional `tool_call`, optional `final_answer`) generated via vLLM `StructuredOutputsParams(json=AgentResponse.model_json_schema())`. Dedicated `generate_json()` in inference layer; no XML, no custom parsing. Model output is parsed with `AgentResponse.model_validate_json()`.
- **Why**: Zero parsing errors (valid JSON by construction), guaranteed stop when schema is satisfied, token savings vs XML tags, and a `thought` field for ReAct-style reasoning. Clear API split: `generate_text()` for free-form text, `generate_json()` for all schema-based outputs (agent, image synthesis, video fusion).
- **Consequences**: Backend session flow uses `generate_json` and `AgentResponse`; XML and regex parsing removed. Tests mock `generate_json` with JSON strings. ADR 024 format no longer supported.
- **Superseded by**: ADR 026 for session tool-calling flow when `LLM_SERVER_URL` is set. ADR 025 still applies to in-process fallback and non-agent `generate_json` use cases (image synthesis, video fusion).

## 026. Session Agent: LlamaIndex + SGLang (External LLM API)
- **Date**: 2026-02-24
- **Context**: The custom ReAct loop with guided JSON (ADR 025) required manual parsing, heuristic recovery, and manual tool-result concatenation. Running vLLM in-process in the backend was an anti-pattern for production. Qwen 2.5 supports native function calling when served via OpenAI-compatible API.
- **Decision**: When `LLM_SERVER_URL` is set, use **LlamaIndex FunctionAgent** (workflow-based) + **SGLang** (OpenAI-compatible server) for session chat. SGLang provides RadixAttention (prompt caching) for faster repeated tool-calling turns. Tools are wrapped as `FunctionTool`; native function calling replaces guided JSON. When `LLM_SERVER_URL` is unset, fall back to in-process ReAct loop (ADR 025).
- **Why**: Eliminates parsing/recovery code, leverages native tool-calling tokens, decouples LLM from backend process, and improves agent performance via SGLang caching.
- **Consequences**: New `sglang` service in docker-compose; `backend/session_agent.py`; `LLM_SERVER_URL` config. Backend depends on SGLang for session chat when configured.
- **Update (2026-02-24)**: Migrated from deprecated `FunctionCallingAgentWorker` to `FunctionAgent` (`llama_index.core.agent.workflow.function_agent`) for compatibility with newer LlamaIndex versions.

## 027. Unified SGLang for All Text LLM Inference
- **Date**: 2026-02-24
- **Context**: Session chat (ADR 026) used SGLang via `LLM_SERVER_URL`, while other AI calls (generate_text, generate_json, stream, chat completions, image synthesis, video fusion, transcript cleanup) used in-process vLLM. Two different inference paths caused inconsistency and duplicated GPU load.
- **Decision**: Route **all text LLM inference** through SGLang. Add `backend/sglang_client.py` with `generate_text`, `generate_json`, `stream_generate_text`, and message-based variants. Remove in-process vLLM from backend; `LocalInferenceService` delegates text generation to the SGLang client. Same schema: `LLM_SERVER_URL`, `HF_MODEL_TEXT`, OpenAI-compatible API.
- **Why**: Single inference engine, consistent schema, decoupled backend from text model lifecycle. SGLang runs in its own container; backend remains lightweight for vision, audio, embeddings.
- **Consequences**: Backend no longer runs vLLM for text. `LLM_SERVER_URL` required at startup. Backend `depends_on: sglang` in docker-compose. Vision (SmolVLM2), audio (faster-whisper), embeddings remain in backend.

## 028. Session Agent: Multi-Stage Pipeline (Intent → Fetch → Synthesize)
- **Date**: 2026-02-24
- **Context**: The single FunctionAgent (ADR 026) mixed intent understanding, tool selection, and answer synthesis in one loop. Users needed clearer tool selection rules (person named → find_chat_by_contact_name; no person → get_last_message) and media-aware replies (include Download URL and Description).
- **Decision**: Replace the single FunctionAgent with a **3-stage pipeline**: (1) **Intent**: LLM extracts structured intent (`person_name`, `limit`, `query_type`) via `generate_json` and `SessionIntent` schema; (2) **Fetch**: Python code calls `get_last_messages` based on intent (no LLM); (3) **Synthesize**: LLM compiles tool result into final answer with media rules. Uses `backend.sglang_client` directly for Stage 1 and Stage 3.
- **Why**: Clear separation of concerns, deterministic tool selection, media-aware synthesis, and minimal token usage (2 LLM calls instead of multi-turn agent loop).
- **Consequences**: `backend/session_agent.py` refactored; LlamaIndex FunctionAgent removed from session flow. Prompts split into `SESSION_INTENT_PROMPT` and `SESSION_SYNTHESIS_PROMPT`. Supersedes the single-agent flow in ADR 026 for session chat.

## 029. Name Search: LLM Nominative + Prefix Matching
- **Date**: 2026-02-24
- **Context**: Slavic suffix-based name matching (`_derive_slavic_name_bases`) was brittle (false positives like "Мария" → "Мара"), required constant exception maintenance, and struggled with multilingual contact databases (RU/UK/Latin).
- **Decision**: (1) Add rule to `SESSION_INTENT_PROMPT`: LLM must always extract person names in Nominative case (Именительный падеж / Називний відмінок) with capital letter. (2) Replace `name_search_variants` + substring `%variant%` with `build_multilingual_prefix_patterns` + prefix `prefix%` matching. Use existing transliteration (Latin ↔ Cyrillic RU/UK) to generate prefix patterns for all scripts.
- **Why**: LLM handles grammar; prefix matching avoids suffix heuristics and works across declensions (Алиса, Алису, Алисой all start with "Алис"). Simpler, more reliable.
- **Consequences**: Removed `_derive_slavic_name_bases`, `_SLAVIC_NAME_ENDINGS`, `_SLAVIC_MASCULINE_GENITIVE`. Prefix match may not find chat titles where name appears mid-string (e.g. "Чат з Алісою"); acceptable for v1.

## 030. Model-Aware Task Queue for Media Processing
- **Date**: 2026-02-26
- **Context**: VLM (~2 GB) and ASR/Whisper (~1.5 GB) models loaded in the backend could exhaust GPU VRAM when both are resident simultaneously. Media processing was inline during Telegram fetch, blocking data collection on model inference.
- **Decision**: Introduce a three-phase ETL pipeline and a model-aware scheduler:
    1. **Phase 1 (Fetch)**: ETL downloads media files and creates `ProcessingTask` objects submitted to the backend via `/tasks/enqueue`. No model inference during fetch.
    2. **Phase 2 (Process)**: Backend `ModelScheduler` (background asyncio task) groups tasks by `model_type` (vision, audio, document), loads one model at a time, drains its queue, unloads, and proceeds to the next.
    3. **Phase 3 (Enrich)**: ETL retrieves results via `/tasks/results/{job_id}`, enriches raw_documents with descriptions/transcripts, then runs indexing and extraction.
- **Why**: Prevents OOM by ensuring only one heavy model is GPU-resident at a time. Decouples data collection speed from inference throughput. Enables batch processing of same-type media.
- **Consequences**:
    - New files: `backend/task_queue.py`, `backend/scheduler.py`.
    - New endpoints: `/tasks/enqueue`, `/tasks/seal/{job_id}`, `/tasks/status/{job_id}`, `/tasks/results/{job_id}`.
    - `LocalInferenceService` gains `unload_vision()` and `unload_audio()` methods.
    - In-memory task queues (lost on backend restart); acceptable for v1.
    - `MediaReindexSource` also uses the queue pattern instead of inline inference.

## 031. Model Orchestrator API Gateway
- **Date**: 2026-02-28
- **Context**: `sglang` (text), `whisper` (audio), and `smolvlm` (vision) models need to be served, but keeping them all loaded simultaneously causes Out-Of-Memory (OOM) errors on limited VRAM hardware. We needed a way to dynamically swap models while presenting a uniform API to the rest of the system.
- **Decision**: Introduce a `model_orchestrator` service that acts as an OpenAI-compatible reverse proxy. It has access to the Docker socket (`/var/run/docker.sock`) and automatically stops/starts the specific model containers (`sglang_text`, `sglang_vision`, `whisper_server`) based on incoming API requests (`/v1/chat/completions` for text/vision, `/v1/audio/transcriptions` for audio).
- **Why**: 
    1.  **VRAM Management**: Enforces strict mutual exclusion between heavy model containers.
    2.  **Simplified Backend**: The `backend` service no longer manages ML models directly via `torch` or `transformers`. It simply makes HTTP calls to the orchestrator.
    3.  **Unified Protocol**: All internal services (ETL, Backend) communicate exclusively via the standard OpenAI REST protocol.
    4.  **Graceful Failback**: The orchestrator returns HTTP `503 Service Unavailable` with a `Retry-After` header if a requested model is blocked by an active, long-running task on another model, preventing timeouts and allowing the client to handle the retry.
- **Consequences**:
    -   New `model_orchestrator` service in `docker-compose.yml`.
    -   Backend `requirements.txt` stripped of heavy ML libraries.
    -   `LocalInferenceService` completely refactored to use HTTP clients instead of native HuggingFace pipelines.
    -   Model swapping taking 5-15 seconds per switch requires tolerant API clients.

## 032. Deterministic NLP Preprocessing Pipeline Before LLM Intent
- **Date**: 2026-03-06
- **Context**: The LLM session agent struggled with robust extraction of localized Cyrillic names (RU/UK) and temporal references within chat search contexts, occasionally hallucinating parameters or misconstruing intent (e.g. "what has Alisa set"). Depending purely on the LLM to parse names, entity grammar, and relative dates resulted in high latency, unreliability, and deep prompt engineering bloat.
- **Decision**: Decouple entity, time, and candidate text extraction from LLM execution by creating a 5-stage deterministic NLP pipeline within the Session Agent workflow:
    1. **Normalization**: Clean text and strip URLs/usernames.
    2. **Candidate Extraction**: Rules (regex) + `natasha` (RU) + optionally `lang-uk/roberta-large-ner-uk` transformers (UK).
    3. **Entity Resolution**: Map candidates to schema contacts using `pymorphy3` for grammar resolution and database matches.
    4. **Time Parsing**: Determine relative date ranges using `dateparser` logic customized for RU/EN mapping.
    5. **Intent Classification (LLM)**: Let the LLM strictly determine the structural intent (e.g. search, media, summary) decoupled from parsing identity fields out of the string.
- **Why**: By shielding the LLM from string grammar resolution, intent parsing becomes far more reliable, predictable, and cost-effective. Deterministic tools (dateparser, natasha) handle language edge-cases much better out-of-the-box.
- **Consequences**:
    -   `NLP_PIPELINE_ENABLED` flag manages the toggle inside `shared/config.py`.
    -   Introduces dependencies: `transformers`, `torch`, `natasha`, `dateparser`, `pymorphy3`.
    -   Reduces the size of `SESSION_INTENT_PROMPT` logic.
    -   Entities are injected directly into pipeline state resulting in faster overall LLM context processing.

## 033. Model Orchestrator Fail-Fast State Resilience
- **Date**: 2026-03-07
- **Context**: The `model_orchestrator` service experienced state desynchronization when `sglang` containers took too long to capture CUDA graphs (exceeding the hardcoded 120s `health_timeout`). This left the orchestrator in a zombie state where it thought a container was running, but it actually timed out, leading to unrecoverable `Name or service not known` DNS errors on subsequent requests.
- **Decision**: 
    1. Bump `health_timeout` to `600` seconds to safely accommodate GPU graph caching and model loading overheads (especially for larger models like Qwen 2.5 7B).
    2. Implement defensive try/except in `_do_switch_mode`: if the mode switch fails for *any* reason (API error or timeout), the `state.current_mode` is eagerly set to `None`.
- **Why**: Prevents the state machine from being permanently poisoned by a transient startup failure. The orchestrator must never cache a "running" state if the health check didn't fully succeed.
- **Consequences**:
    - The first request after a startup crash will take longer because it has to re-trigger the container startup sequence instead of instantly failing, but the system is able to self-heal.
