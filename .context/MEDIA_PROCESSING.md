# Media Processing

## Overview

Summagram автоматически обрабатывает медиа файлы из Telegram сообщений, извлекая текст, метаданные и семантическую информацию для последующего поиска и анализа.

## Supported Media Types

### 📷 Images (Photos)
- **Формат**: JPG
- **Обработка**: Анализ через vision модель (SmolVLM2 или LLaVA)
- **Извлекаемая информация**:
  - Описание содержимого изображения
  - Классификация: мем / не мем
  - Классификация: портрет / не портрет
  - Теги для категоризации
  - Публичный URL для доступа

### 🎵 Audio & Voice Messages
- **Форматы**: OGG (voice), MP3 (audio)
- **Обработка**: Транскрипция через **faster-whisper** (в 4x быстрее стандартного Whisper).
- **Особенности**:
  - Voice Activity Detection (VAD) для удаления тишины.
  - Автоопределение языка.
  - Постобработка: очистка транскрипта от слов-паразитов и исправление пунктуации через LLM.

### 📄 Documents
- **Форматы**: PDF, DOCX, PPTX, XLSX.
- **Обработка**: Извлечение текста и таблиц через **kreuzberg**.
- **Особенности**:
  - Сохранение структуры таблиц.
  - Высокая скорость (до 50x быстрее аналогов).
  - Поддержка OCR для сканированных файлов.

### 🎬 Video
- **Обработка**: Метаданные (без анализа содержимого)
- **Извлекаемая информация**:
  - Длительность
  - Разрешение (ширина × высота)
  - Размер файла
  - MIME-тип

  ## Processing Pipeline (Three-Phase, ADR 030)

Media processing uses a **model-aware task queue** to prevent GPU OOM. Only one heavy model (VLM or Whisper) is loaded at a time.

### Phase 1: Fetch (ETL)
- ETL detects media in Telegram messages via Telethon API.
- Media files are downloaded to `/app/storage/media/` with naming `tg_{chat_id}_{message_id}.{extension}`.
- For each downloaded file, a `ProcessingTask` is submitted to the backend via `POST /tasks/enqueue` (no model inference during fetch).
- Raw documents are saved to the DB with placeholder metadata (type, path, but no description).

### Phase 2: Process (Backend ModelScheduler)
- The `ModelScheduler` background task groups pending tasks by `model_type` (vision, audio, document).
- It loads one model at a time, processes all tasks of that type, then unloads and moves to the next.
- Priority order: vision > audio > document.
- ETL polls `GET /tasks/status/{job_id}` until all tasks are complete.

### Phase 3: Enrich (ETL)
- ETL fetches results via `GET /tasks/results/{job_id}`.
- Raw documents are updated in the DB with descriptions, transcripts, and analysis metadata.
- Indexing (embeddings) and structured event extraction run on the enriched documents.

### Backend Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/tasks/enqueue` | POST | Submit a processing task |
| `/tasks/seal/{job_id}` | POST | Signal all tasks submitted |
| `/tasks/status/{job_id}` | GET | Poll completion status |
| `/tasks/results/{job_id}` | GET | Retrieve analysis results |

### Metadata Storage
Analysis results are stored in `TelegramMediaMetadata`:

```python
class TelegramMediaMetadata(BaseModel):
    type: str  # photo, audio, voice, document, video
    extension: Optional[str]
    path: Optional[str]
    description: Optional[str]  # Результат анализа
    size: Optional[int]
    mime: Optional[str]
    
    # Audio-specific
    duration: Optional[float]
    title: Optional[str]
    performer: Optional[str]
    
    # Image-specific
    is_meme: Optional[bool]
    is_portrait: Optional[bool]
    tags: Optional[List[str]]
    url: Optional[str]
    
    # Document-specific
    page_count: Optional[int]
```

### 5. Content Integration
Медиа информация интегрируется в content строку документа:

```
[PHOTO] A sunset over the ocean with palm trees
[AUDIO TRANSCRIPT] Hello, this is a voice message about...
[DOCUMENT] Contract text... | Pages: 5
```

## Configuration

### Backend Models

```yaml
# docker-compose.yml
backend:
  environment:
    HF_MODEL_AUDIO: "large-v3"  # faster-whisper model size
    HF_MODEL_VISION: "HuggingFaceTB/SmolVLM2-Instruct"
```

### Ollama (для LLaVA)

```bash
# Установка модели
ollama pull llava

# Проверка доступности
curl http://localhost:11434/api/tags
```

## Logging

Детальное логирование для каждого типа медиа:

```
🎬 MEDIA PROCESSING STARTED for message 12345
============================================================
📷 Processing PHOTO for msg 12345 in chat 67890
  ✓ Downloaded photo to: /app/storage/media/tg_67890_12345.jpg
  🔍 Analyzing image with vision model...
  ✓ Image analysis complete:
    - Description: A beautiful sunset over the ocean...
    - Is meme: False
    - Is portrait: False
    - Tags: ['nature', 'sunset', 'ocean']
    - URL: http://backend:8000/media/tg_67890_12345.jpg

📦 FINAL MEDIA INFO:
  Type: photo
  Size: 245678 bytes
  Path: /app/storage/media/tg_67890_12345.jpg
  Description length: 156 chars
  Content prefix: [PHOTO] A beautiful sunset over the ocean...
============================================================
```

## Reindexing

### Manual Reindexing via UI

The Next.js frontend provides a dedicated button for batch media reprocessing:

1. Navigate to the **Datasets** view in the sidebar.
2. Click the **Reprocess All Media** button in the top right header.
3. Observe the **ETL Progress Footer** slide up from the bottom for real-time tracking of progress and specific sub-tasks (e.g., "Indexing 20 documents...").

### API Endpoint

```bash
# Запуск переиндексации
POST http://etl:8000/reindex-media  # Internal
POST http://localhost:8002/reindex-media # External

# Ответ
{
  "job_id": "uuid-here",
  "status": "queued"
}

# Проверка статуса
GET http://etl:8000/jobs/{job_id}
GET http://localhost:8002/jobs/{job_id}
```

## Performance

### Faster-Whisper
- **Скорость**: 4x быстрее стандартного Whisper
- **Точность**: Сопоставима с оригинальным Whisper
- **Особенности**: VAD, автоопределение языка, beam search

### Kreuzberg
- **Скорость**: 10-50x быстрее PyPDF2, pdfplumber
- **Возможности**: Таблицы, изображения, OCR
- **Поддержка**: PDF, Office форматы

### LLaVA
- **Качество**: Превосходит SmolVLM2 для сложных изображений
- **Требования**: Ollama сервис
- **Использование**: Опционально, fallback на SmolVLM2

## Error Handling

Все этапы обработки медиа защищены try-except блоками:

1. **Download failure**: Логируется ошибка, медиа пропускается
2. **Analysis failure**: Сохраняется путь к файлу без описания
3. **Timeout**: 120s timeout для анализа документов
4. **Retry logic**: 3 попытки с экспоненциальной задержкой

## Vision-Language Pipeline (Qwen First)

The system uses a deterministic multi-stage pipeline for media analysis, prioritizing the **Qwen2.5-VL-3B-Instruct** model.

### Image Analysis (Deterministic CoT)
Processing follows four consistent stages:
1. **Classification**: Identify image type (selfie, meme, generic, document).
2. **Description**: Generate a factual visual description of the scene.
3. **Conditional OCR**: Extract text if the image is identified as a meme or document.
4. **Synthesis**: Combine all inputs into a structured JSON using constrained decoding (`guided_json`).

### Video Analysis (Dual Stream)
Video processing is optimized using a "Smart Sampling" strategy:
1. **Visual Stream**: 
   - **Scene Detection**: Uses `PySceneDetect` to extract keyframes at scene changes.
   - **Adaptive FPS**: Falls back to fixed-rate sampling for static content.
2. **Audio Stream**: Parallel extraction via `ffmpeg` and transcription via `Whisper`.
3. **Temporal Fusion**: Synthesis of visual logs and audio transcripts into a temporal summary with structured segments.

### Model Selection Strategy
- **Core (Default)**: `Qwen2.5-VL-3B-Instruct` (AWQ/GPTQ) for images and video.
- **Scanner (Fallback)**: `MiniCPM-o 2.6` for dense document OCR.
- **Artist (Optional)**: `LFM2-VL-3B` for detailed artistic descriptions.

### Resource Management
- **Model Scheduler**: `backend/scheduler.py` loads one model at a time (vision or audio), drains its queue, unloads with `gc.collect()` + `torch.cuda.empty_cache()`, then proceeds.
- **GPU Semaphore**: Sequential access via `asyncio.BoundedSemaphore` manages VRAM consumption within a model's processing batch.
- **Smart Resizing**: Images are proportionally resized to a maximum dimension (e.g., 1024px) before VLM processing to minimize token usage and VRAM.
