import os
from piccolo.conf.apps import AppConfig
from etl.tables import (
    UnifiedEvent,
    SyncState,
    RawDocument,
    DownloadRange,
    IndexedDocument,
    Chat,
    Contact,
    ChatMember,
    SocialGraphCache,
    SessionTable,
    ChatSegment,
    ChatSegmentAnalysis,
)

APP_CONFIG = AppConfig(
    app_name="etl",
    migrations_folder_path=os.path.join(os.path.dirname(__file__), "migrations"),
    table_classes=[
        UnifiedEvent,
        SyncState,
        RawDocument,
        DownloadRange,
        IndexedDocument,
        Chat,
        Contact,
        ChatMember,
        SocialGraphCache,
        SessionTable,
        ChatSegment,
        ChatSegmentAnalysis,
    ],
    migration_dependencies=[],
    commands=[],
)
