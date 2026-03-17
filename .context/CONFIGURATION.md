# Configuration Guide

This document describes the environment variables used to configure the Summagram services (`backend`, `etl`, `frontend`). Configuration is managed via `.env` files and loaded by `config.py`.

## 1. Telegram Credentials (Mandatory)

Required for the ETL service to connect to Telegram.

| Variable | Required | Description |
| :--- | :--- | :--- |
| `TELEGRAM_API_ID` | **Yes** | API ID from [my.telegram.org](https://my.telegram.org). |
| `TELEGRAM_API_HASH` | **Yes** | API Hash from [my.telegram.org](https://my.telegram.org). |
| `TELEGRAM_PHONE` | **Yes** | Phone number (international format) used for the initial session login. |

## 2. AI Configuration

### Embedding Settings

Used for semantic search (RAG).

| Variable | Default | Description |
| :--- | :--- | :--- |
| `EMBEDDING_PROVIDER` | `local` | `local` (HuggingFace), `openai`, `ollama` |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Model ID. For `local`, use HF hub ID. For `openai`, use `text-embedding-3-small`. |

### LLM Settings (Text Generation)

Used for chat assistance and event extraction.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `openrouter` | `openrouter`, `openai`, `ollama`, `local` (vLLM). |
| `LLM_MODEL` | (Provider dependent) | Model ID (e.g., `google/gemini-2.0-flash-001`). Overrides provider defaults. |
| `LLM_API_KEY` | - | API Key for external providers. Not needed for `ollama` / `local`. |
| `LLM_API_BASE` | (Provider dependent) | Base URL. Defaults: OpenRouter (`https://openrouter.ai/api/v1`), Local (`http://localhost:11434/v1`). |
| `CONTEXT_WINDOW` | `60000` | Max context window size in tokens. |

### Local Inference (vLLM & VLM)

Only used if `LLM_PROVIDER=local` or for Image Analysis in Backend.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `VLLM_GPU_UTILIZATION` | `0.7` | GPU memory fraction (0.0 - 1.0). |
| `HF_MODEL_TEXT` | `Qwen/Qwen2.5-Coder-7B-Instruct` | vLLM engine model. |
| `HF_MODEL_MEDIA` | `HuggingFaceTB/SmolVLM2-2.2B-Instruct` | Transformers vision model. |
| `VISION_PROVIDER` | `local` | `local` (SmolVLM2) or `ollama` (LLaVA). |
| `OLLAMA_VISION_MODEL` | `llava` | Model name to use if `VISION_PROVIDER=ollama`. |
| `HF_MODEL_AUDIO` | `openai/whisper-large-v3-turbo` | Faster-whisper model. |
| `MAX_CONTEXT_LEN` | `8192` | Max model length for local inference. |

## 3. Database & Storage

| Variable | Default | Description |
| :--- | :--- | :--- |
| `DB_PATH` | `summagram.db` | Path to the SQLite database. |
| `CHROMA_DB_PATH` | `./chroma_data` | Path to persistent ChromaDB. |
| `CHROMA_DB_IP` | `localhost` | Hostname of ChromaDB service (Docker: `chroma`). |
| `CHROMA_DB_PORT` | `8000` | Port of ChromaDB service. |
| `MEDIA_BASE_URL` | `/media` | Public URL prefix for serving media files. |

## 4. App Settings

| Variable | Default | Description |
| :--- | :--- | :--- |
| `DISCOVERY_DAYS` | `90` | Lookback period for chat discovery. |
| `CALDAV_URL` | - | (Optional) URL for Calendar sync. |
| `CALDAV_USERNAME` | - | (Optional) Username for Calendar sync. |
| `CALDAV_PASSWORD` | - | (Optional) Password for Calendar sync. |
| `CORS_ORIGINS` | `*` | Allowed origins for backend API. |

## 5. Observability (OpenTelemetry)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `OTEL_ENABLED` | `false` | Set to `true` to enable tracing. |
| `OTEL_EXPORTER_OTLP_ENDPOINT`| `http://localhost:4317` | Endpoint for OTLP collector (Jaeger). |

## Usage Scenarios

### Scenario A: Fully Local (Privacy Focused)
Run everything on your own hardware (Requires GPU).
```ini
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
TELEGRAM_PHONE=...

EMBEDDING_PROVIDER=local
LLM_PROVIDER=local
HF_MODEL_TEXT=Qwen/Qwen2.5-Coder-7B-Instruct
HF_MODEL_MEDIA=HuggingFaceTB/SmolVLM2-2.2B-Instruct
```

### Scenario B: Hybrid (Power & Cost Balanced)
Use external LLM for smarts, local Embeddings/VLM for speed/privacy.
```ini
TELEGRAM_API_ID=...
...

EMBEDDING_PROVIDER=local
LLM_PROVIDER=openrouter
LLM_MODEL=google/gemini-2.0-flash-001
LLM_API_KEY=sk-or-v1-...
```

### Scenario C: Debugging
enable OpenTelemetry to trace requests.
```ini
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
```
