# Frontend Service (V0)

Frontend-часть Summagram построена на базе Next.js и React, используя современные UI-киты для обеспечения "премиального" пользовательского опыта.

## Основные представления (Views)

-   **SessionsView ([sessions-view.tsx](../v0/components/views/sessions-view.tsx)):** Главный экран для AI-сессий. Позволяет создавать новые сессии и взаимодействовать с AI-ассистентом.
-   **ChatView ([chat-view.tsx](../v0/components/views/chat-view.tsx)):** Просмотр истории конкретного Telegram-чата.
-   **DatasetsView ([datasets-view.tsx](../v0/components/views/datasets-view.tsx)):** Управление проиндексированными данными, фильтрация по типам медиа (фото, видео, аудио).
-   **NetworkView ([network-view.tsx](../v0/components/views/network-view.tsx)):** Визуализация социального графа (связей между контактами).
-   **PipelineView ([pipeline-view.tsx](../v0/components/views/pipeline-view.tsx)):** Мониторинг текущих задач ETL (синхронизация, индексация).

## Взаимодействие с Backend

Frontend общается с Backend и ETL через централизованный API-клиент:
-   [api.ts](../v0/lib/api.ts): Содержит методы для вызова всех эндпоинтов (Fetch, Post).

## Особенности UI
-   **Shadcn/UI**: Используется библиотека компонентов для Radix UI.
-   **Dark Mode**: Полная поддержка темной темы.
-   **Responsive Design**: Адаптивная верстка для разных размеров экранов.
-   **Real-time status**: Использование хуков для периодического опроса статуса ETL-задач.
