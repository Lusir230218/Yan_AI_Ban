import asyncio
from sqlalchemy import text
from core.database import engine


async def test():
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        print("数据库连接成功:", result.scalar())

        tables = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        rows = tables.fetchall()
        if rows:
            print("已存在的表:", [r[0] for r in rows])
        else:
            print("数据库中暂无表")


asyncio.run(test())
