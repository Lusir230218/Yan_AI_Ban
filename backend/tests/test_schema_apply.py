"""阶段五·2A 集成测：apply Neo4j schema 后查询约束/索引存在。

需 dev Neo4j 起（bolt://localhost:7687 或 settings.NEO4J_HOST 配置）。
通过 KG_ENV=dev 显式触发。
测试自身会确保 `kg-dev` 数据库存在（CREATE DATABASE IF NOT EXISTS）。
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _kg_env_dev():
    """会话级固定 KG_ENV=dev。"""
    old = os.environ.get("KG_ENV")
    os.environ["KG_ENV"] = "dev"
    yield
    if old is None:
        os.environ.pop("KG_ENV", None)
    else:
        os.environ["KG_ENV"] = old


@pytest.fixture(scope="session")
def target_db() -> str:
    """目标 database 名 = kg-dev。"""
    from kg.neo4j_client import _database_name
    return _database_name()


@pytest.fixture(scope="session")
async def _ensure_kg_dev(target_db):
    """确保目标数据库存在（用 system db 建）。session scope."""
    from neo4j import AsyncGraphDatabase
    from config import settings

    drv = AsyncGraphDatabase.driver(
        f"neo4j://{settings.NEO4J_HOST}:{settings.NEO4J_PORT}",
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )
    try:
        async with drv.session(database="system") as s:
            r = await s.run("SHOW DATABASES")
            existing = {row["name"] async for row in r}
            if target_db not in existing:
                await s.run(f"CREATE DATABASE `{target_db}` IF NOT EXISTS WAIT")
    finally:
        await drv.close()
    return target_db


@pytest.fixture
async def driver():
    """每个 test 独立 driver + 重置全局 singleton, 避免 pytest-asyncio 跨 loop socket 关闭问题。"""
    from neo4j import AsyncGraphDatabase
    from config import settings
    drv = AsyncGraphDatabase.driver(
        f"neo4j://{settings.NEO4J_HOST}:{settings.NEO4J_PORT}",
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )
    try:
        yield drv
    finally:
        await drv.close()
        # kg_session() 内部用模块级 _driver singleton, 这里也 reset 让下次重连
        from kg.neo4j_client import close_kg_driver
        await close_kg_driver()


# session 退出时不主动 close driver——让 pytest 进程退出自动 GC 即可
# 避免 close 后下一个 test 拿到 None driver


# ===== 纯函数测试 =====

def test_database_name_kg_dev():
    from kg.neo4j_client import current_database
    assert current_database() == "kg-dev"


def test_database_switch_by_kg_env(monkeypatch):
    from kg.neo4j_client import current_database
    monkeypatch.setenv("KG_ENV", "dev")
    assert current_database() == "kg-dev"
    monkeypatch.setenv("KG_ENV", "staging")
    assert current_database() == "kg-staging"
    monkeypatch.setenv("KG_ENV", "production")
    assert current_database() == "neo4j"


def test_drop_requires_dev(monkeypatch):
    """prod 环境调 drop_kg_schema 必须抛错——纯逻辑不需要 connect。"""
    from kg.schema import drop_kg_schema
    monkeypatch.setenv("KG_ENV", "production")
    with pytest.raises(RuntimeError):
        import asyncio
        asyncio.run(drop_kg_schema())
    monkeypatch.setenv("KG_ENV", "dev")


# ===== 集成测（连真 Neo4j） =====

@pytest.mark.asyncio
async def test_init_creates_constraints_and_indexes(_ensure_kg_dev, driver):
    from kg.schema import init_kg_schema
    from config import settings

    await init_kg_schema(embedding_dim=settings.EMBEDDING_DIM)

    async with driver.session(database="kg-dev") as s:
        consts = await s.run("SHOW CONSTRAINTS")
        names = {row["name"] async for row in consts}
        assert "concept_id" in names
        assert "concept_type_name" in names

        idxs = await s.run("SHOW INDEXES")
        idx_names = {row["name"] async for row in idxs}
        for need in ("concept_type", "concept_confidence",
                     "concept_status", "concept_subject",
                     "concept_search", "concept_embedding"):
            assert need in idx_names, f"missing index: {need}"


@pytest.mark.asyncio
async def test_insert_concept_then_fulltext_query(_ensure_kg_dev, driver):
    """apply schema 后能 insert 节点 + 被全文索引召回。"""
    from kg.schema import init_kg_schema
    from config import settings
    await init_kg_schema(embedding_dim=settings.EMBEDDING_DIM)

    async with driver.session(database="kg-dev") as s:
        await s.run("""
            MATCH (c:Concept {id: 'method:test-schema-apply'})
            DETACH DELETE c
        """)
        # pre-compute embedding in Python (Cypher 不支持 [0.1] * N)
        dim = settings.EMBEDDING_DIM
        emb = [0.1] * dim
        await s.run("""
            MERGE (c:Concept {id: 'method:test-schema-apply'})
            SET c.name = 'schema-apply-test', c.type = 'Method',
                c.subject = 'math-calc',
                c.embedding = $emb
        """, emb=emb)
        hits = await s.run("""
            CALL db.index.fulltext.queryNodes('concept_search', 'schema-apply-test')
            YIELD node RETURN node.id AS id
        """)
        ids = [row["id"] async for row in hits]
        assert "method:test-schema-apply" in ids
