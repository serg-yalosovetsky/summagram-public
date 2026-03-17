# Backend Service (Core API)

Backend-сервис действует как основной шлюз (gateway) между Frontend и базами данных/AI-моделями. Всю тяжелую вычислительную работу по генерации он делегирует на `orchestrator` и специализированные ML-микросервисы `sglang` / `whisper`.

## API Reference

### 1. Данные и чаты

| Эндпоинт | Метод | Описание | Параметры |
| :--- | :--- | :--- | :--- |
| `/chats` | GET | Список чатов | `limit`, `offset`, `min_importance` |
| `/contacts` | GET | Список контактов | `limit`, `offset` |
| `/chat/{source_id}` | GET | Детали чата | `source_id` (int) |
| `/contact/{source_id}` | GET | Детали контакта | `source_id` (int) |
| `/chat/{source_id}/messages` | GET | Сообщения чата | `source_id`, `limit`, `offset` |
| `/documents` | GET | Все документы | `limit`, `offset` |

### 2. AI Сессии

| Эндпоинт | Метод | Описание | Параметры (Body) |
| :--- | :--- | :--- | :--- |
| `/sessions` | GET | Список сессий | `limit`, `offset` |
| `/sessions` | POST | Новая сессия | `id`, `title`, `context_chat_id`, `meta` |
| `/session/{id}` | GET | Детали сессии | `session_id` (str) |
| `/session/{id}/messages`| GET | Сообщения сессии| `session_id`, `limit`, `offset` |
| `/session/{id}/messages`| POST | Сообщение в чат | `content`, `context_chat_id` |

### 3. Инференс и анализ

| Эндпоинт | Метод | Описание | Параметры (Body) |
| :--- | :--- | :--- | :--- |
| `/generate` | POST | Ген. текста | `prompt`, `system_prompt`, `max_tokens`, `temperature` |
| `/analyze-image` | POST | Анализ фото | `image_path` (str), `prompt` (optional) |
| `/analyze-video` | POST | Анализ видео | `video_path` (str), `adaptive_fps`, `use_scene_detection` |
| `/transcribe-audio`| POST | Транскрибация | `audio_path` (str) |
| `/analyze-pdf` | POST | Анализ PDF | `pdf_path` (str) |
| `/v1/embeddings` | POST | Векторы (OAI) | `input` (str\|list), `model` |
| `/v1/chat/completions`| POST | Чат (OAI) | `messages`, `model`, `stream`, `temperature` |

### 4. Системные

| Эндпоинт | Метод | Описание |
| :--- | :--- | :--- |
| `/health` | GET | Проверка статуса |
| `/config` | GET | Текущая конфигурация |
| `/config` | POST | Обновление конфига (`VISION_PROVIDER`) |

## Структура файлов
-   [main.py](../backend/main.py): Определение API эндпоинтов и жизненного цикла приложения.
-   [service.py](../backend/service.py): Бизнес-логика, управление сессиями, интеграция RAG.
-   [test_inference_logic.py](../backend/tests/test_inference_logic.py): Пример тестов, взаимодействующих с API `sglang` и `backend`.

## Особенности
-   **Микросервисная ML-архитектура**: Тяжелые модели вынесены в отдельные сервисы-воркеры Docker Compose (`sglang`, `sglang_vision`, `whisper`). Backend получает готовый результат без риска OOM в собственном процессе.
-   **Streaming:** Поддержка Server-Sent Events (SSE) в связке с `sglang` для плавного отображения текста по мере генерации в интерфейсе чата.
-   **Сессионный Процессинг**: Запросы по RAG прогоняются через 5-стадийный детерминированный NLP-пайплайн (нормализация, извлечение кандидатов `natasha`, разрешение сущностей `pymorphy3`, парсинг времени `dateparser`) перед тем, как `SessionAgent` извлекает финальный intent пользователя и выбирает инструменты (получение истории чата, контекста и т.д.).
