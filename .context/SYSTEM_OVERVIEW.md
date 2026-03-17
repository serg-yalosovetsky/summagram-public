# System Overview

## High-Level Goal
Summagram is a **Modular Agentic RAG system** designed to ingest personal communication history (initially Telegram), extract structured life events (Debts, Interviews, Reminders), and integrate them with actionable tools (Calendar, Dashboards) in a secure, local-first manner.

## Core Entities
- **Source**: An external provider of raw data (e.g., Telegram Chat, Gmail).
- **Document**: A normalized, source-agnostic representation of a message or file.
- **Event**: A structured entity extracted from usage (e.g., `DebtEvent`, `InterviewEvent`) with start/end times and payloads.
- **SyncState**: Tracks the incremental progress of each source to avoid re-fetching old data.

## Modules Map

### Backend Service (`backend/`)
-   **`main.py`**: FastAPI entry point. Exposes endpoints for inference and embeddings to the frontend.
-   **`inference.py`**: A thin HTTP client layer that communicates with the `model_orchestrator` for all text, vision, and audio tasks.
-   **`task_queue.py` & `scheduler.py`**: Manages asynchronous processing queues for media and routes tasks to the orchestrator.
-   **`models.py`**: Shared Pydantic definitions (event schemas).
-   **`telemetry.py`**: Observability initialization.

### Model Orchestrator (`model_orchestrator/`)
- **`main.py`**: FastAPI entry point. Lifespan calls `startup_orchestrator` / `shutdown_orchestrator`.
- **`config.py`**: `MODE_URLS` dict, env lookups for `TEXT_VLLM_URL`, `VISION_VLLM_URL`, `VLLM_API_KEY`.
- **`models.py`**: `OrchestratorState` (with `engine_states`, `last_used_at`, `vision_idle_task`), Pydantic response schemas.
- **`exceptions.py`**: Typed domain exceptions (`UnknownModeError`, `WorkerWakeTimeoutError`, `WorkerReadyTimeoutError`, `WorkerSleepError`).
- **`services.py`**: `EngineState` enum, vLLM control plane (`is_sleeping`, `sleep_engine`, `wake_engine`, `wait_openai_ready`), singleflight `ensure_mode`, `classify_openai_payload` deterministic router, vision idle auto-sleep timer, `startup_orchestrator` / `shutdown_orchestrator`.
- **`utils.py`**: Legacy / manual-ops Docker SDK helpers — NO LONGER on the hot path.
- **`middleware.py`**: `ProxyMiddleware` — streaming reverse-proxy.
- **`router.py`**: Route handlers including `GET /debug/orchestrator`.
- **vLLM Sleep/Wake**: Both `text-vllm` and `vision-vllm` containers run permanently with `--enable-sleep-mode`. Switching is done via HTTP `POST /sleep` / `POST /wake_up` — never `docker stop/start`. Text stays awake; vision sleeps at level 2 after 30s idle.

### ETL Service (`etl/`)
-   **`main.py`**: FastAPI entry point for job management and source control.
-   **`manager.py`**: Job Orchestrator. Manages async sync tasks.
-   **`sources/`**: Adapters for data sources (Telegram). Fetches media.
-   **`processing/`**: Transformation logic (Indexing, Extraction). Injects media context into nodes.
-   **`chat_analysis/`**: Segment-based batch analysis pipeline using LLMs to infer topics, events, and relationship topology from dialogs.
-   **`llm_config.py`**: Configures connection to the Orchestrator for LLM/Embeddings.
-   **`db/`**: Centralized database interactions using Piccolo ORM and `asyncpg`.

### Frontend Service (`v0/`)
-   **Next.js Frontend**: Primary, modern UI built with Next.js, Radix UI, and lucide-react. Located in the `v0/` directory.
-   **Components**:
    -   `app-shell/`: Core layout components including `EtlFooter` for real-time background task tracking.
    -   `views/`: Feature-specific views (Dashboard, Network, Datasets, etc.).
-   **SSE Streaming**: Global `AppContext` monitors `activeJobId` and subscribes to backend EventSource streams to drive real-time UI updates (like the `EtlFooter` progress bar) without polling.
-   **Social Graph**: Visualization of user connections using `react-force-graph-2d`.

---

### Legacy Frontend (`frontend/`)
-   **Streamlit App**: `app.py` coordinates legacy UI modules. Used primarily for initial prototyping and internal tools.

### ETL Service (`etl/`)
-   **`main.py`**: FastAPI entry point.
-   **`manager.py`**: Background job management and orchestration.
-   **`processing/`**:
    -   `telegram_etl.py`: Core logic for Telegram message processing and indexing.
    -   `graph.py`: Social graph analysis and community detection.
-   **`db/`**: Central repository layer for both ETL and Backend. Manages `raw_documents`, `chats`, `contacts`, `sessions`, and `social_graph_cache` using Piccolo ORM and asyncpg.

### Shared / Libraries
-   **PostgreSQL**: Shared relational database used by all services, managed via Piccolo migrations in `etl/migrations/`.
-   **`storage/media`**: Shared volume for local storage of audio, images, and documents.

## Infrastructure
- **Docker**:
    -   **`model-orchestrator`**: Unified API Gateway. Controls vLLM workers via HTTP sleep/wake.
    -   **`text-vllm`**: Always-on vLLM OpenAI-compatible server (`--enable-sleep-mode`). Stays awake by default.
    -   **`vision-vllm`**: Always-on vLLM multimodal server. Sleeps at level 2 when idle; woken on vision requests.
    -   **`backend`**: Application logic, scheduling, and RAG (FastAPI).
    -   **`frontend`**: Next.js web application.
    -   **`etl`**: Job processor for data ingestion and graph analysis.
    -   **`chroma`**: Vector store for RAG.
    -   **`jaeger`**: Shared OTLP observability node.

## Detailed Documentation
- [Database Schema](DB_SCHEMA.md): Detailed description of tables and data models.
- [API Contracts](API_CONTRACTS.md): Specification of the backend and ETL API endpoints.
- [User Stories](USER_STORIES.md): End-to-end interaction flows and service communication.
- [Configuration Guide](CONFIGURATION.md): Environment variables and settings reference.
- [Media Processing](MEDIA_PROCESSING.md): Media file processing pipeline and supported formats.
