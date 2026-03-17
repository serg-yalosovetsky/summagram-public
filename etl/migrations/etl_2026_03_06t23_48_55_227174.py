from piccolo.apps.migrations.auto.migration_manager import MigrationManager

ID = "2026-03-06T23:48:55:227174"
VERSION = "1.33.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="", description=DESCRIPTION
    )

    async def run():
        from etl.db.core import get_db
        async with get_db() as conn:
            await conn.execute("ALTER TABLE chat_segments DROP CONSTRAINT IF EXISTS uq_chat_segments_chat_id_segment_no;")
            await conn.execute("ALTER TABLE chat_segments ADD CONSTRAINT uq_chat_segments_chat_id_segment_no UNIQUE (chat_id, segment_no);")

    manager.add_raw(run)

    return manager
