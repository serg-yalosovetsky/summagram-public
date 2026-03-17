# API Contracts

This document outlines the API endpoints exposed by the Summagram Backend Service.

**Base URL**: `http://localhost:8003` (Default)

## Service: Backend (`summagram-backend`)

The backend service provides local inference capabilities (LLM generation, Image Analysis, Embeddings) via FastAPI.

### Health Check
**GET** `/health`
Returns the operational status of the service and the loaded model.

### Chat Completions (OpenAI Compatible)
**POST** `/v1/chat/completions`
Generates chat responses. Supports streaming. (Note: In the new architecture, calls to this endpoint should ideally go directly to the `model_orchestrator` service, or the backend proxying them to it).

### Embeddings (OpenAI Compatible)
**POST** `/v1/embeddings`
Generates vector embeddings for a given input text.

### Image Analysis
**POST** `/analyze-image`
Analyzes an image using a robust 4-stage deterministic pipeline. Returns description and structured analysis (JSON).

### Video Analysis
**POST** `/analyze-video`
Analyzes video content using smart sampling and dual-stream pipeline. Returns temporal summary and transcript.

### Audio Transcription
**POST** `/transcribe-audio`
Transcribes audio using faster-whisper.

### PDF & Document Analysis
**POST** `/analyze-pdf`
Analyzes research papers, PDFs, or Office documents using kreuzberg.

### Database Access (Repository Layer)
- **GET** `/chats`: List chats with importance filter.
- **GET** `/contacts`: List user contacts.
- **GET** `/chats/{id}`: Detailed chat info.
- **GET** `/contacts/{id}`: Detailed contact info.
- **GET** `/messages/{id}`: Fetch message history for a chat.
- **GET** `/documents`: List all raw documents (Datasets).

### Task Queue (Media Processing)
- **POST** `/tasks/enqueue`: Submit a media-processing task to the model-aware queue.
- **POST** `/tasks/seal/{job_id}`: Signal that all tasks for this job have been submitted.
- **GET** `/tasks/status/{job_id}`: Get completion status for a job's media tasks.
- **GET** `/tasks/status/stream/{job_id}`: Server-Sent Events (SSE) stream for real-time task completion status.
- **GET** `/tasks/results/{job_id}`: Retrieve final processing results.

### Configuration
- **GET** `/config`: Returns current backend/inference configuration.
- **PATCH** `/config`: Updates configuration at runtime.

## Service: Model Orchestrator (`model_orchestrator`)

The `model_orchestrator` acts as an intelligent API Gateway and drop-in replacement for OpenAI endpoints, dynamically routing requests to underlying specialized local inference servers (`sglang_text`, `sglang_vision`, `whisper`) to conserve GPU VRAM.

**Base URL**: `http://localhost:8004` (Default external) / `http://model-orchestrator:8000` (Internal Docker)

### Chat Completions (OpenAI API Compatible)
**POST** `/v1/chat/completions`
Identical to the standard OpenAI chat completions endpoint.
- **Routing Logic**: The orchestrator inspects the payload. If an `image_url` is detected in the `messages`, it routes the request to the Vision model (`sglang_vision`). Otherwise, it routes to the Text model (`sglang_text`). Supports streaming (SSE).

### Audio Transcriptions (OpenAI API Compatible)
**POST** `/v1/audio/transcriptions`
Identical to the standard OpenAI audio transcriptions endpoint. Routes the audio file to the `whisper` service for transcription.

### Models Check (OpenAI API Compatible)
**GET** `/v1/models`
Returns the currently active model. The response `data` array contains a `ModelObject` with the active container name as `id`. Empty when no model is loaded.

### Health Check
**GET** `/health`
Lightweight liveness probe (used by Docker healthcheck). Returns `{"status": "ok"}`.

### Detailed Status
**GET** `/status`
Returns detailed orchestrator status: current mode, whether a mode switch is in progress (`switching`), and the list of available modes (`text`, `vision`, `audio`).

---

## Service: ETL (`etl`)

### Health Check
**GET** `/health`

### Job Management
**POST** `/jobs/{source_type}`: Submit ingestion job. returns `{job_id: string, status: "queued"}`.
**GET** `/jobs/{job_id}`: Get current job status/progress.
**GET** `/jobs/stream/{job_id}`: Server-Sent Events (SSE) stream for real-time job status updates.
Returns `JobStatus` (or streams it as SSE JSON `data:`):
```json
{
  "job_id": "uuid",
  "status": "queued | running | completed | failed",
  "progress": 0.0,
  "message": "Step description",
  "result": {},
  "error": null
}
```

### Source Control
**GET** `/sources/{source_type}/dialogs`: List available chats from source (e.g., Telegram).

### Chat Analysis
**POST** `/analyze-chats`: Run chat analysis (description + tags) for the given chats only. Request body must include a non-empty `chat_ids` array (e.g. from the dialog selection). Returns `{job_id: string, status: "queued"}`. Progress and completion are visible via **GET** `/jobs/{job_id}`.
- Request: `{ "chat_ids": number[] }` (required, non-empty).
- Response: `{ "job_id": string, "status": "queued" }`.
- 400 if `chat_ids` is missing or empty.

### Media Management
**POST** `/reindex-media`: Trigger batch reprocessing of existing media files.

### Social Graph
**POST** `/graph/build`: Trigger social graph and interest cluster analysis.
**GET** `/graph/data`: Retrieve cached social graph JSON for visualization.
