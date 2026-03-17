# Model Orchestrator Service

Сервис `model_orchestrator` выступает в роли умного API Gateway, задача которого — управлять двумя всегда-запущенными vLLM-воркерами с помощью HTTP sleep/wake эндпоинтов, экономя VRAM без полной остановки контейнеров.

## Архитектура

Оба контейнера (`text-vllm`, `vision-vllm`) работают постоянно, с флагом `--enable-sleep-mode`. Переключение — это HTTP-вызов, а не `docker stop/start`:

```
frontend
   |
   v
orchestrator  (единый OpenAI-compatible вход, порт 8004)
   ├── text-vllm   [обычно awake]         порт 8000 (внутренний)
   └── vision-vllm [обычно sleep level 2] порт 8000 (внутренний)
```

### Sleep/Wake политика

- При старте: `text-vllm` → `wake_up`, `vision-vllm` → `sleep(level=2)`
- Text-запросы идут напрямую в `text-vllm`, не трогая vision.
- Vision-запрос: `wake_up` → wait `/v1/models == 200` → проксируем → таймер 30 сек → `sleep(level=2)`.
- `text-vllm` никогда не усыпляется принудительно.

### Детерминированный роутер

`classify_openai_payload(payload)` проверяет, есть ли в `messages` item с `type == "image_url"` или `"input_image"`. Никакого LLM-классификатора.

## API Reference

| Эндпоинт | Метод | Описание |
| :--- | :--- | :--- |
| `/v1/chat/completions` | POST | Роутинг на `text-vllm` или `vision-vllm` по содержимому payload |
| `/v1/audio/transcriptions` | POST | Проксируется напрямую на `whisper` |
| `/v1/models` | GET | Возвращает текущий активный режим |
| `/health` | GET | Liveness check (Docker healthcheck) |
| `/status` | GET | Текущий режим, состояния движков, singleflight |
| `/warm` | POST | Разбудить воркер вручную |
| `/debug/orchestrator` | GET | Live `engine_states`, `last_used_ago_sec`, `warm_task_active` |

## Конфигурация

| Переменная | Описание | По умолчанию |
| :--- | :--- | :--- |
| `TEXT_VLLM_URL` | URL text-воркера | `http://text-vllm:8000` |
| `VISION_VLLM_URL` | URL vision-воркера | `http://vision-vllm:8000` |
| `VLLM_API_KEY` | API ключ для vLLM | `local-dev-key` |
| `AUDIO_URL` | URL Whisper | `http://summagram_whisper_server:8000` |
| `HF_MODEL_TEXT` | Модель для text-vllm | `Qwen/Qwen2.5-Coder-7B-Instruct` |
| `HF_MODEL_MEDIA` | Модель для vision-vllm | `Qwen/Qwen2.5-VL-3B-Instruct` |
| `HUGGING_FACE_HUB_TOKEN` | HF токен | (из `.env`) |

## Безопасность

`VLLM_SERVER_DEV_MODE=1` открывает `/sleep`, `/wake_up`, `/is_sleeping` — они доступны **только** из внутренней `llm` Docker-сети. Наружу смотрит только оркестратор.

## Структура файлов

- [main.py](../model_orchestrator/main.py): FastAPI entry point. Lifespan → `startup_orchestrator` / `shutdown_orchestrator`.
- [config.py](../model_orchestrator/config.py): `MODE_URLS`, env-переменные для vLLM URL и API ключа.
- [models.py](../model_orchestrator/models.py): `OrchestratorState` (с `engine_states`, `last_used_at`, `vision_idle_task`), Pydantic response schemas.
- [exceptions.py](../model_orchestrator/exceptions.py): `UnknownModeError`, `WorkerWakeTimeoutError`, `WorkerReadyTimeoutError`, `WorkerSleepError`.
- [services.py](../model_orchestrator/services.py): `EngineState`, control plane (`is_sleeping`, `sleep_engine`, `wake_engine`, `wait_openai_ready`), singleflight `ensure_mode`, `classify_openai_payload`, vision idle timer.
- [utils.py](../model_orchestrator/utils.py): **Legacy / manual-ops only** — Docker SDK хелперы, больше не используются в hot path.
- [middleware.py](../model_orchestrator/middleware.py): `ProxyMiddleware` — потоковое проксирование.
- [router.py](../model_orchestrator/router.py): Обработчики маршрутов + `/debug/orchestrator`.
