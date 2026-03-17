from piccolo.conf.apps import AppRegistry
from piccolo.engine.postgres import PostgresEngine
from shared.config import Config

DB = PostgresEngine(
    config={
        "dsn": getattr(
            Config,
            "POSTGRES_DSN",
            "postgresql://summagram:fYfzQ9qdv2qLYYyD3jOF0z7yc2PyFVIFj57LrJI%2BJ50%3D@localhost:8432/summagram",
        )
    }
)

APP_REGISTRY = AppRegistry(apps=["etl.piccolo_app"])
