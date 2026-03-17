# Алгоритмы Индексации и Детальный ETL Процессинг

Summagram использует многоступенчатый конвейер обработки данных. Ниже приведено детальное описание процессов для каждого типа данных, используемых функций и параметров моделей.

## 1. Текстовые сообщения (Telegram Chats)

Основной алгоритм: **Context Windowing** (контекстная группировка).

*   **Файл:** [telegram_etl.py](../etl/processing/telegram_etl.py)
*   **Главная функция:** `transform_telegram_docs_to_nodes(docs, context_window_size=3)`
*   **Процесс:**
    1.  Сообщения сортируются по чату (`source_id`) и времени.
    2.  Для каждого сообщения создается "окно" из предыдущих `context_window_size` сообщений.
    3.  Текст обогащается: к текущему сообщению добавляется блок `--- PREVIOUS MESSAGES ---`.
    4.  Применяется `mask_pii()` для защиты персональных данных.
*   **Модель эмбеддингов:** `BAAI/bge-small-en-v1.5` (локально через HuggingFace).
*   **Параметры:** `context_window_size=3` (по умолчанию).

## 2. Изображения (Photos)

Алгоритм: **Deterministic Multi-stage VLM Pipeline**.

*   **Файл:** [inference.py](../backend/inference.py)
*   **Главная функция:** `LocalInferenceService.analyze_image(image_path)`
*   **Модель:** `Qwen2.5-VL-3B-Instruct-AWQ` (через Vision Processor).
*   **Этапы и функции:**
    1.  **Сжатие:** `resize_image_smart` для оптимизации VRAM.
    2.  **Классификация:** `_analyze_image_transformers` с промптом `STAGE_1_CLASSIFY`.
    3.  **Описание:** Определение объектов и действий через промпт `STAGE_2_DESCRIBE`.
    4.  **OCR:** Выполняется только если тип определен как "meme", "document" или "text" (`STAGE_3_OCR`).
    5.  **Синтез:** Итоговое объединение в структурированный JSON через `guided_json` (pydantic-схема `ImageAnalysisResult`).
*   **Параметры:** `max_new_tokens=500`, `temperature=0.4`, `top_p=0.9`.

## 3. Видеофайлы

Алгоритм: **Dual Stream Fusion & Visual Search Indexing**.

*   **Файл:** [inference.py](../backend/inference.py)
*   **Главная функция:** `LocalInferenceService.analyze_video(request)`
*   **Процесс:**
    1.  **Аудио-поток:** Экстракция звука (`extract_audio`) и транскрибация (`transcribe_audio`).
    2.  **Визуальный-поток:**
        *   Детекция сцен (`extract_keyframes_scene_detection`) или фиксированный FPS.
        *   Выбор до 10 ключевых кадров (`max_frames=10`).
        *   Описание каждого кадра через Vision-модель.
        *   Генерация визуальных эмбеддингов через **CLIP** (`openai/clip-vit-base-patch32`) для поиска по картинке.
    3.  **Fusion (Слияние):**
        *   Stage 1: Построение хронологии (`VIDEO_FUSION_STEP_1_TIMELINE`).
        *   Stage 2: Финальный саммари в формате JSON (`VideoAnalysisResult`).
*   **Хранение:** Визуальные векторы сохраняются в отдельную коллекцию ChromaDB `video_visual_search`.

## 4. Голосовые сообщения и Аудио

Алгоритм: **High-precision ASR with LLM Cleanup**.

*   **Файл:** [inference.py](../backend/inference.py)
*   **Главная функция:** `LocalInferenceService.transcribe_audio(audio_path)`
*   **Модель:** `faster-whisper` (модель: `whisper-large-v3-turbo`).
*   **Технические параметры:**
    *   `beam_size=5` для точности.
    *   `vad_filter=True` (Voice Activity Detection) для игнорирования тишины.
    *   `compute_type="float16"` (на GPU) или `"int8"` (на CPU).
*   **Пост-обработка:** Если текст длиннее 5 слов, вызывается LLM (`Qwen2.5-3B`) для "чистки" транскрипта (удаление слов-паразитов, исправление пунктуации) через промпт `TRANSCRIPT_CLEANUP`.

## 5. Документы (PDF)

Алгоритм: **Structured Markdown Ingestion**.

*   **Файл:** [inference.py](../backend/inference.py)
*   **Главная функция:** `analyze_pdf_with_kreuzberg(pdf_path)`
*   **Инструмент:** Библиотека `kreuzberg`.
*   **Особенности:**
    *   Автоматическое определение и извлечение таблиц.
    *   OCR-fallback: если PDF состоит из картинок, запускается оптическое распознавание.
    *   Результат возвращается в виде текста, метаданных и списка извлеченных изображений.

## 6. Социальный Граф

*   **Файл:** [graph.py](../etl/processing/graph.py)
*   **Главная функция:** `GraphAnalyzer.build()`
*   **Параметры анализа:**
    *   `SIMILARITY_THRESHOLD=0.45`: Порог схожести интересов для проведения связи между пользователями.
    *   `DEFAULT_N_CLUSTERS=5`: Количество тематических групп (KMeans).
    *   `EMBEDDING_BATCH_SIZE=32`: Размер батча при запросе векторов у Backend.
