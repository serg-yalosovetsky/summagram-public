# Tech Stack & Conventions

## Languages & Frameworks
- **Language**: Python 3.12+, TypeScript
- **Dependency Management**: `uv` / Standard `pip` and `pnpm` for frontend.
- **Web Framework**: 
    -   **Frontend**: Next.js (App Router), React, Radix UI, lucide-react.
    -   **Backend**: FastAPI (Async).
-   **LLM Orchestration**: vLLM OpenAI-compatible server (`--enable-sleep-mode`) managed by model-orchestrator via HTTP sleep/wake.
-   **Embeddings**: Local `HuggingFaceEmbedding` (hosted in Backend).
-   **Styling**: TailwindCSS & Radix UI.

## Libraries
- **Logging**: `loguru`.
- **Inference**: `vLLM` (model-orchestrator workers; `text-vllm` and `vision-vllm`), `torch`, `transformers`.
- **Media Processing**:
    -   **VLM**: Qwen2.5-VL-3B-Instruct (Primary), MiniCPM-o 2.6 (Scanner), LFM2-VL-3B (Artist).
    -   **Video**: PySceneDetect (Scene Detection), FFmpeg (Extraction).
    -   **Preprocessing**: OpenCV (cv2), Pillow.
    -   **ASR**: Faster-Whisper (Large-v3-Turbo).
    -   **PDF**: Kreuzberg.
- **Database**: 
    - `PostgreSQL` / `asyncpg` / `Piccolo ORM` (Relational).
    - `chromadb` (Vector).
- **Validation**: `Pydantic v2`.
- **Telegram**: `Telethon` (ETL/Source).
- **Observability**: `OpenInference` + `OpenTelemetry` + `Jaeger`.
- **HTTP Client**: `httpx` (Async).
- **Graph Analysis**: `NetworkX` for social graph construction.

## Infrastructure
- **Microservices**: Docker Compose orchestration.
- **Volumes**: Named volumes for ML models (`huggingface_cache`) and shared media (`storage/media`).

## Conventions
- **Async First**: All I/O (DB, Network, Telegram) must be asynchronous (`async`/`await`).
- **Lazy Loading**: Heavy models (LLM/Embeddings) should differ initialization until first use.
- **Idempotency**: Extraction logic must check if an event exists (via `evidence_msg_id`) before insertion.
- **Security**: 
    - Untrusted input (chats) MUST be passed through `security.wrap_user_data()` before reaching the LLM.
    - Prompts use ChatML format with `<im_start>` and `<im_end>` tags.
- **Modular Sources**: New sources must inherit from `sources.base.BaseSource`.
- **Privacy**: PII (Emails, Phones) must be masked using `security.mask_pii()` before displaying in the UI.
- **Pydantic**: ALWAYS WHEN POSSIBLE SHOULD BE USED PYDANTIC MODELS INSTEAD OF DICT.
- **Prompts**: ALL prompts must live as class attributes of `Prompts` in `backend/prompts.py`. Never define module-level prompt constants in other files. JSON schemas are NOT embedded in prompt text — they are passed via `generate_json(json_schema=...)` at call time.

