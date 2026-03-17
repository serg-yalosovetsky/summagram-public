from piccolo.apps.migrations.auto.migration_manager import MigrationManager
from piccolo.columns.column_types import BigInt
from piccolo.columns.column_types import Integer

ID = "2026-03-06T13:18:29:314830"
VERSION = "1.32.0"
DESCRIPTION = ""


async def forwards():
    manager = MigrationManager(
        migration_id=ID, app_name="etl", description=DESCRIPTION
    )

    manager.alter_column(
        table_class_name="Chat",
        tablename="chats",
        column_name="source_id",
        db_column_name="source_id",
        params={},
        old_params={},
        column_class=BigInt,
        old_column_class=Integer,
        schema=None,
    )

    manager.alter_column(
        table_class_name="Contact",
        tablename="contacts",
        column_name="source_id",
        db_column_name="source_id",
        params={},
        old_params={},
        column_class=BigInt,
        old_column_class=Integer,
        schema=None,
    )

    manager.alter_column(
        table_class_name="ChatMember",
        tablename="chat_members",
        column_name="chat_id",
        db_column_name="chat_id",
        params={},
        old_params={},
        column_class=BigInt,
        old_column_class=Integer,
        schema=None,
    )

    manager.alter_column(
        table_class_name="ChatMember",
        tablename="chat_members",
        column_name="user_id",
        db_column_name="user_id",
        params={},
        old_params={},
        column_class=BigInt,
        old_column_class=Integer,
        schema=None,
    )

    manager.alter_column(
        table_class_name="SessionTable",
        tablename="sessions",
        column_name="context_chat_id",
        db_column_name="context_chat_id",
        params={},
        old_params={},
        column_class=BigInt,
        old_column_class=Integer,
        schema=None,
    )

    return manager
