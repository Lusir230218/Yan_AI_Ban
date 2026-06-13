from __future__ import annotations

from typing import AsyncIterator
from contextlib import asynccontextmanager

from neo4j import AsyncGraphDatabase, AsyncDriver

from config import settings

_driver: AsyncDriver | None = None


def _get_bolt_url() -> str:
    return f"neo4j://{settings.NEO4J_HOST}:{settings.NEO4J_PORT}"


async def get_kg_driver() -> AsyncDriver:
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
    await get_kg_driver()
    yield
    await close_kg_driver()
