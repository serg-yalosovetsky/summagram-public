import asyncio
from etl.db.core import get_db

async def check_schema():
    async with get_db() as conn:
        res = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'chat_members'")
        print("Columns in chat_members:")
        for row in res:
            print(f"- {row['column_name']}")

if __name__ == "__main__":
    asyncio.run(check_schema())
