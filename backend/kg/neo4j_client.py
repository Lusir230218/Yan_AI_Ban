from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession

from config import settings


_driver: AsyncDriver | None = None


def _get_bolt_url() -> str:
    return f"neo4j://{settings.NEO4J_HOST}:{settings.NEO4J_PORT}"


def _database_name() -> str:
    """根据 KG_ENV 切换 database 名（dev/staging/prod 物理隔离）。

    注意：读 `settings.KG_ENV` 而不是 `os.getenv("KG_ENV")` —
    Pydantic BaseSettings 把 .env 加载到 `settings` 对象，但不写回 os.environ，
    所以直接 os.getenv() 会拿到 None 然后 fallback 到 "production"。
    """
    from config import settings
    env = (settings.KG_ENV or "production").lower()
    return {
        "production": "neo4j",
        "staging":    "kg-staging",
        "dev":        "kg-dev",
    }.get(env, "neo4j")


def current_database() -> str:
    """测试 / 调试用：返回当前连接的 database 名"""
    return _database_name()


async def get_kg_driver() -> AsyncDriver:
    """单例 driver。首次调用 verify_connectivity。"""
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            _get_bolt_url(),
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
        await _driver.verify_connectivity()
    return _driver


async def close_kg_driver() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


@asynccontextmanager
async def kg_lifespan() -> AsyncIterator[None]:
    """原有 lifespan 入口——保留以便不破坏 main.py 旧引用。"""
    await get_kg_driver()
    yield
    await close_kg_driver()


@asynccontextmanager
async def kg_session(database: str | None = None) -> AsyncIterator[AsyncSession]:
    """所有 Neo4j 操作统一入口。database 默认由 KG_ENV 决定。

    用法：
        # 默认：走 KG_ENV 切换（2B/2C 用 kg-dev）
        async with kg_session() as s:
            await s.run(...)

        # 显式覆盖：planner_agent 等老代码强制走默认 neo4j 库
        async with kg_session(database="neo4j") as s:
            await s.run(...)

    Args:
        database: 显式指定 database 名。None 时用 `_database_name()`（KG_ENV 决定）。
    """
    driver = await get_kg_driver()
    db_name = database if database is not None else _database_name()
    async with driver.session(database=db_name) as session:
        yield session
