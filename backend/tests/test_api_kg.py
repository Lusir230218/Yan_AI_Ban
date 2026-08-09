"""Knowledge Graph API 集成测 — 通过 AsyncClient + 真实 DB（NullPool）。

走通：
1. POST /api/v1/kg/search      — 端到端 GraphRAG（mock LLM + mock Neo4j）
2. POST /api/v1/feedback/kg-answer — 写入 feedback_kg_answer
3. POST /api/v1/feedback/kg-answer — rating=1 且 cited_concepts=[] → 400
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker


@pytest.fixture(autouse=True)
async def _ensure_feedback_tables():
    """测试环境如果还没建 feedback_kg_answer / gap_questions 表，幂等创建。

    conftest 的 client fixture 不触发 lifespan，所以 create_all 不会自动跑。
    用 conftest 的 _test_engine 而不是 prod engine，避免跨 engine 连接冲突。
    """
    from core.database import Base
    from models import feedback  # noqa: F401  side-effect import

    # 用 conftest 的 _test_engine 创建（保证和测试 session 同一个连接池）
    from tests.conftest import _test_engine

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture(autouse=True)
def _reset_graph_rag_singleton():
    """每个测试前清掉 GraphRAG 单例，确保 chat_json patch 生效。"""
    from api.v1 import knowledge_graph
    knowledge_graph.reset_graph_rag()
    yield
    knowledge_graph.reset_graph_rag()


# ===== /kg/search =====


@pytest.mark.asyncio
async def test_kg_search_endpoint(auth_client, test_user, db):
    """完整 RAG 调用：mock LLM 直接返回结构化 JSON。"""
    fake_llm = AsyncMock(return_value={
        "answer": "建议先复习 [不定积分] ...",
        "cited": [{"id": "kp:MA-INT-001",
                   "name": "不定积分", "type": "KP"}],
    })

    # mock Neo4j session — 用 _patch_neo4j_session 复用测试 helper
    seed_rows = [{
        "id": "kp:MA-INT-001", "name": "不定积分", "type": "KP",
        "subject": "math-calc", "pg_kp_id": None,
        "confidence": 0.9, "score": 0.95,
    }]
    call_count = {"n": 0}

    async def fake_run(query, **params):
        call_count["n"] += 1
        r = MagicMock()
        r.data = AsyncMock(return_value=seed_rows if call_count["n"] == 1 else [])
        r.single = AsyncMock(return_value=None)
        return r

    inner_session = MagicMock()
    inner_session.run = fake_run
    neo4j_cm = MagicMock()
    neo4j_cm.__aenter__ = AsyncMock(return_value=inner_session)
    neo4j_cm.__aexit__ = AsyncMock(return_value=None)

    # mock PG
    pg_inner = MagicMock()
    pg_inner.execute = AsyncMock()
    pg_inner.execute.return_value.all.return_value = []
    pg_inner.commit = AsyncMock()
    pg_cm = MagicMock()
    pg_cm.__aenter__ = AsyncMock(return_value=pg_inner)
    pg_cm.__aexit__ = AsyncMock(return_value=None)

    # mock embed_call
    fake_embed = AsyncMock(return_value=[0.1] * 4)

    with patch("kg.graph_rag.kg_session", return_value=neo4j_cm), \
         patch("kg.graph_rag.async_session", return_value=pg_cm), \
         patch("kg.llm_client.chat_json", new=fake_llm), \
         patch("kg.embedding_pipeline.embed_text", new=fake_embed):
        resp = await auth_client.post(
            "/api/v1/kg/search",
            json={"query": "如何学换元法"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "cited" in body
    assert "answer" in body
    assert "fallback" in body
    # 至少引用 1 条
    assert len(body["cited"]) >= 1


@pytest.mark.asyncio
async def test_kg_search_unauthenticated_rejected(client):
    """未带 Authorization → 401。"""
    resp = await client.post(
        "/api/v1/kg/search",
        json={"query": "test"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_kg_search_empty_query_rejected(auth_client):
    """空 query → 422 (Pydantic min_length=1)。"""
    resp = await auth_client.post(
        "/api/v1/kg/search",
        json={"query": ""},
    )
    assert resp.status_code == 422


# ===== /feedback/kg-answer =====


@pytest.mark.asyncio
async def test_feedback_positive_with_cited_writes_row(auth_client, test_user, db):
    """rating=1 + cited_concepts → 写库成功，query_hash 存在。"""
    cited = [{"id": "kp:MA-INT-001", "name": "不定积分", "type": "KP"}]
    query_text = f"换元法 {uuid.uuid4().hex[:6]}"  # 避免 hash 冲突
    resp = await auth_client.post(
        "/api/v1/feedback/kg-answer",
        json={
            "query": query_text,
            "answer": "建议先复习不定积分",
            "cited_concepts": cited,
            "rating": 1,
        },
    )
    assert resp.status_code == 200, resp.text

    # 验证写库
    row = (await db.execute(text("""
        SELECT rating, cited_concepts, query_hash
        FROM feedback_kg_answer
        WHERE user_id = :u ORDER BY id DESC LIMIT 1
    """), {"u": test_user.id})).first()
    assert row is not None
    assert row.rating == 1
    assert "kp:MA-INT-001" in (row.cited_concepts or [])
    assert len(row.query_hash) == 16


@pytest.mark.asyncio
async def test_feedback_negative_without_cited_works(auth_client, test_user):
    """rating=-1（👎）即使无 cited_concepts 也允许（用户可以点 👎 不填理由）。"""
    resp = await auth_client.post(
        "/api/v1/feedback/kg-answer",
        json={
            "query": "test",
            "answer": "答错了",
            "cited_concepts": [],
            "rating": -1,
        },
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_feedback_requires_cited_for_positive_rating(auth_client):
    """rating=1 但 cited_concepts=[] → 400。"""
    resp = await auth_client.post(
        "/api/v1/feedback/kg-answer",
        json={
            "query": "x",
            "answer": "y",
            "cited_concepts": [],
            "rating": 1,
        },
    )
    assert resp.status_code == 400
    assert "cited_concepts" in resp.text or "赞" in resp.text


@pytest.mark.asyncio
async def test_feedback_invalid_rating_rejected(auth_client):
    """rating=2 (超出 -1..1) → 422。"""
    resp = await auth_client.post(
        "/api/v1/feedback/kg-answer",
        json={
            "query": "x",
            "answer": "y",
            "cited_concepts": [{"id": "a", "name": "A", "type": "KP"}],
            "rating": 2,
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_feedback_unauthenticated_rejected(client):
    """未带 Authorization → 401。"""
    resp = await client.post(
        "/api/v1/feedback/kg-answer",
        json={
            "query": "x", "answer": "y",
            "cited_concepts": [], "rating": 0,
        },
    )
    assert resp.status_code == 401