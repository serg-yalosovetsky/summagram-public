# ETL Service (Data Processing)

ETL-сервис — это "мозг" системы, отвечающий за сбор, трансформацию и индексацию данных из Telegram.

## Основные компоненты и функции

### 1. Источники данных (Sources)
-   **Файл:** [telegram.py](../etl/sources/telegram.py)
-   **Класс:** `TelegramSource`
-   **Ключевые функции:**
    *   `get_dialogs(limit)`: Получает список чатов пользователя.
    *   `process_chats(params)`: Основной цикл скачивания сообщений и медиа.

### 2. Обработка (Processing)
-   **Indexer ([indexer.py](../etl/processing/indexer.py)):**
    *   `update_index(docs)`: Точка входа для индексации. Вызывает трансформацию в ноды и вставку в ChromaDB.
    *   `get_chat_engine()`: Создает интерфейс для RAG-чата с настроенным системным промптом.
-   **Extractor ([extractor.py](../etl/processing/extractor.py)):**
    *   `extract_and_save(docs)`: Перебирает документы и пытается извлечь события с помощью LLM (функции `debt`, `interview`, `topup`).
-   **Chat Analyzer (`etl/chat_analysis/`)**:
    *   `segmenter.py`: Разбивает историю чата на логические сегменты (`chat_segments`) без пересечений по стратегиям (`time_gap`, `max_msgs`, `token_budget`).
    *   `service.py`: Конвейер для глубокого семантического анализа каждого сегмента (топики, люди, события) и агрегации в финальное описание чата (`ChatAggregateAnalysis`) и контактов (`ContactAggregateAnalysis`).
-   **Graph Analyzer ([graph.py](../etl/processing/graph.py)):**
    *   `build(force_rebuild)`: Полный цикл построения графа: агрегация -> эмбеддинги -> схожесть -> кластеризация.


### 3. API Reference

#### Управление задачами (Jobs)

| Эндпоинт | Метод | Описание |
| :--- | :--- | :--- |
| `/jobs/{source_type}` | POST | Запуск задачи импорта для указанного типа источника |
| `/jobs/{job_id}` | GET | Получение статуса задачи по ID |

**`POST /jobs/{source_type}`**
- **Path params:** `source_type` — тип источника (напр. `telegram`)
- **Body:** `JobSubmitRequest`
  ```json
  { "params": { "chat_ids": [123, 456], "limit": 100 } }
  ```
- **Response:** `JobSubmitResponse`
  ```json
  { "job_id": "uuid-string", "status": "queued" }
  ```

**`GET /jobs/{job_id}`**
- **Path params:** `job_id` — ID задачи (UUID)
- **Response:** `JobStatusResponse`
  ```json
  { "job_id": "...", "status": "running", "progress": 0.45, "message": "Processing...", "result": null, "error": null }
  ```

---

#### Обработка данных

| Эндпоинт | Метод | Описание |
| :--- | :--- | :--- |
| `/analyze-chats` | POST | Запуск анализа чатов (описание + теги) |
| `/reindex-media` | POST | Переиндексация медиа файлов |

**`POST /analyze-chats`**
- **Body:** `AnalyzeChatsRequest`
  ```json
  { "chat_ids": [123, 456] }
  ```
- **Response:** `JobSubmitResponse` — задача ставится в очередь
- **Ошибки:** `400` — `chat_ids` пуст или не указан

**`POST /reindex-media`**
- **Body:** `ReindexRequest` (опционально, есть значения по умолчанию)
  ```json
  { "media_types": ["photo", "audio", "document", "voice"], "force_reindex": false }
  ```
  Допустимые значения `media_types`: `photo`, `audio`, `document`, `voice`, `video`.
- **Response:** `JobSubmitResponse`

---

#### Работа с источниками

| Эндпоинт | Метод | Описание |
| :--- | :--- | :--- |
| `/sources/{source_type}/dialogs` | GET | Список чатов из указанного источника |

**`GET /sources/{source_type}/dialogs`**
- **Path params:** `source_type` — тип источника (напр. `telegram`)
- **Query params:** `limit` (int, опционально) — макс. кол-во диалогов
- **Response:**
  ```json
  { "dialogs": [ { "id": 123, "name": "Chat Name", "type": "group", ... } ] }
  ```
- **Ошибки:** `400` — неизвестный тип источника; `503` — не настроены учетные данные Telegram

---

#### Граф и Аналитика

| Эндпоинт | Метод | Описание |
| :--- | :--- | :--- |
| `/graph/build` | POST | Построение / пересборка социального графа |
| `/graph/data` | GET | Получение кешированных данных графа |

**`POST /graph/build`**
- **Query params:** `force_rebuild` (bool, default `false`) — принудительная полная пересборка
- **Response:** Результат построения графа (JSON)

**`GET /graph/data`**
- **Response:** `GraphData`
  ```json
  {
    "nodes": [{ "id": 1, "label": "User", "cluster": 0, "message_count": 42 }],
    "edges": [{ "source": 1, "target": 2, "weight": 0.85, "edge_type": "similarity", "interaction_count": 10 }],
    "clusters": [0, 1],
    "node_count": 2,
    "edge_count": 1
  }
  ```
- **Ошибки:** `404` — граф ещё не построен (нужен `POST /graph/build`)

---

#### Системные

| Эндпоинт | Метод | Описание |
| :--- | :--- | :--- |
| `/health` | GET | Статус сервиса |

**`GET /health`**
- **Response:** `{ "status": "ok", "service": "etl" }`

### 4. Управление задачами (JobManager)
-   **Файл:** [manager.py](../etl/manager.py)
-   Поскольку задачи по индексации могут быть длительными, сервис использует внутреннюю очередь задач (`JobManager`) для асинхронного выполнения и отслеживания статуса.

## Структура файлов
-   [main.py](../etl/main.py): API для управления задачами и получения данных о графе.
-   [database.py](../etl/database.py): Весь DAO слой для работы с SQLite.
-   [manager.py](../etl/manager.py): Логика управления воркерами и очередями.

## Алгоритм работы
1. Пользователь выбирает чаты для синхронизации.
2. ETL создает задачу на загрузку.
3. Сообщения скачиваются и сохраняются в `raw_documents`.
4. Запускается конвейер индексации: текст -> эмбеддинги -> ChromaDB.
5. Параллельно работает экстрактор (Extractor) для извлечения событий, обращаясь за LLM-генерацией к шлюзу Backend (по внутренней сети `http://backend:8000/v1`).
