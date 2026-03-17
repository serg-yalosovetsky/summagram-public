import asyncio
from etl.db.core import get_db

async def run():
    async with get_db() as conn:
        try:
            await conn.execute("ALTER TABLE chat_members DROP CONSTRAINT chat_members_pkey")
        except Exception as e:
            print("Drop failed:", e)

if __name__ == '__main__':
    import os
    os.environ['POSTGRES_DSN'] = "postgresql://summagram:fYfzQ9qdv2qLYYyD3jOF0z7yc2PyFVIFj57LrJI%2BJ50%3D@localhost:8432/test_summagram_etl"
    asyncio.run(run())
