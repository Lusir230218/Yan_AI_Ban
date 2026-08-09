"""graph_rag 单元 / 集成测试 — mock Neo4j + LLM，不依赖真实 DB。

测试目标：
1. retrieve → generate_with_context 端到端（含 structured cited 输出）
2. embed 失败 → 走 fallback 分支
3. vector_recall 跨模型过滤
4. expand_1hop 过滤低 confidence 节点
5. fetch_user_state 阈值（>=0.8 mastered, >=0.5 in_progress, else weak）
6. fallback 写 gap_questions（mock async_session）
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kg.graph_rag import GraphRAG, RetrievedNode


def _fake_llm_out(answer: str = "建议复习不定积分", cited_id: str = "kp:MA-INT-001"):
    return AsyncMock(return_value={
        "answer": answer,
        "cited": [{"id": cited_id, "name": "不定积分", "type": "KP"}],
    })


def _fake_embed(dim: int = 4):
    return AsyncMock(return_value=[0.1] * dim)


def _make_rag(llm_out=None, embed_dim=4):
    return GraphRAG(
        embedding_model="test-embedding",
        embedding_dim=embed_dim,
        llm_call=llm_out or _fake_llm_out(),
        embed_call=_fake_embed(embed_dim),
    )


def _patch_neo4j_session(rows, expanded_rows=None, syllabus_rows=None):
    """构造 mock Neo4j session — async context manager。

    调用顺序：
      1. _vector_recall  → rows
      2. _expand_1hop    → expanded_rows (per seed 返回 dict)
      3. _fallback       → syllabus_rows
    """
    call_count = {"n": 0}

    async def fake_run(query, **params):
        call_count["n"] += 1
        result = MagicMock()
        if call_count["n"] == 1:
            result.data = AsyncMock(return_value=rows)
        elif call_count["n"] == 2:
            result.data = AsyncMock(return_value=expanded_rows or [])
        elif call_count["n"] == 3:
            result.data = AsyncMock(return_value=syllabus_rows or [])
        else:
            result.data = AsyncMock(return_value=[])
        result.single = AsyncMock(return_value=None)
        return result

    # 构造可 async with 的 session 对象
    inner_session = MagicMock()
    inner_session.run = fake_run

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=inner_session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _patch_pg_session(mastery_rows=None, syllabus_rows=None):
    """构造 mock PG session — async context manager。

    第一次 execute() → mastery 行（list of MagicMock）
    第二次 execute() → syllabus fallback 行（list of MagicMock）
    """
    call_count = {"n": 0}

    async def fake_execute(*args, **kwargs):
        call_count["n"] += 1
        result = MagicMock()
        if call_count["n"] == 1:
            result.all = MagicMock(return_value=mastery_rows or [])
        else:
            result.all = MagicMock(return_value=syllabus_rows or [])
        result.first = MagicMock(return_value=None)
        return result

    inner = MagicMock()
    inner.execute = fake_execute
    inner.commit = AsyncMock()

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=inner)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.mark.asyncio
async def test_generate_with_structured_cited():
    """端到端：embed → recall → expand → LLM → {answer, cited}。"""
    rag = _make_rag()

    seed_rows = [
        {"id": "kp:MA-INT-001", "name": "不定积分", "type": "KP",
         "subject": "math-calc", "pg_kp_id": 1, "confidence": 0.9, "score": 0.95},
    ]
    expanded_rows = [{
        "prereqs": [{"id": "def:limit", "name": "极限", "type": "Definition",
                     "subject": "math-calc", "pg_kp_id": None, "confidence": 0.85}],
        "mistakes": [], "contrasts": [],
    }]
    mastery_rows = [
        MagicMock(kp_id=1, score=0.3, correct_count=2, total_count=10),
    ]

    neo4j_cm = _patch_neo4j_session(seed_rows, expanded_rows)
    pg_cm = _patch_pg_session(mastery_rows=mastery_rows)

    with patch("kg.graph_rag.kg_session", return_value=neo4j_cm), \
         patch("kg.graph_rag.async_session", return_value=pg_cm):
        result = await rag.generate_with_context("如何学换元法？", user_id=42)

    assert result.answer  # 模拟 LLM 返回的 answer 非空
    assert result.fallback is False
    assert any(c["id"] == "kp:MA-INT-001" for c in result.cited)
    assert len(result.seeds) >= 1


@pytest.mark.asyncio
async def test_fallback_when_embed_fails():
    """embed 返回空 → fallback 分支。"""
    rag = _make_rag()
    rag.embed_call = AsyncMock(return_value=[])

    neo4j_cm = _patch_neo4j_session([])
    pg_cm = _patch_pg_session()

    with patch("kg.graph_rag.kg_session", return_value=neo4j_cm), \
         patch("kg.graph_rag.async_session", return_value=pg_cm):
        result = await rag.generate_with_context("x", user_id=1)

    assert result.fallback is True


@pytest.mark.asyncio
async def test_vector_recall_missing_index_returns_empty():
    """Neo4j 缺 concept_embedding 向量索引时，_vector_recall 返回空、不抛。

    防御性降级：生产环境未跑 init_kg_schema 时，RAG 应走 fallback 而不是 500。
    """
    from neo4j.exceptions import ClientError

    rag = _make_rag()

    async def fake_run(query, **params):
        r = MagicMock()
        r.data = AsyncMock(side_effect=ClientError(
            "Failed to invoke procedure `db.index.vector.queryNodes`: "
            "Caused by: java.lang.IllegalArgumentException: "
            "There is no such vector schema index: concept_embedding"
        ))
        r.single = AsyncMock(return_value=None)
        return r

    inner = MagicMock()
    inner.run = fake_run
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=inner)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("kg.graph_rag.kg_session", return_value=cm):
        result = await rag._vector_recall([0.1] * 4)

    assert result == []  # 空 list → 上层走 fallback


@pytest.mark.asyncio
async def test_fallback_when_no_seeds():
    """embed 成功但 vector_recall 返回空 → fallback。"""
    rag = _make_rag()
    neo4j_cm = _patch_neo4j_session([])

    pg_cm = _patch_pg_session(syllabus_rows=[
        MagicMock(id="kp:S1", name="syllabus1", type="KP"),
    ])

    with patch("kg.graph_rag.kg_session", return_value=neo4j_cm), \
         patch("kg.graph_rag.async_session", return_value=pg_cm):
        result = await rag.generate_with_context("冷僻问题", user_id=1)

    assert result.fallback is True
    assert "图谱暂未覆盖" in result.answer


@pytest.mark.asyncio
async def test_expand_filters_low_confidence():
    """扩展节点 confidence < 0.4 必须被过滤。"""
    rag = _make_rag()
    seed_rows = [
        {"id": "kp:A", "name": "A", "type": "KP",
         "subject": "math-calc", "pg_kp_id": None, "confidence": 0.9, "score": 0.9},
    ]
    expanded_rows = [{
        "prereqs": [
            {"id": "def:high", "name": "high", "type": "Definition",
             "subject": "math-calc", "pg_kp_id": None, "confidence": 0.85},
            {"id": "def:low", "name": "low", "type": "Definition",
             "subject": "math-calc", "pg_kp_id": None, "confidence": 0.3},
        ],
        "mistakes": [], "contrasts": [],
    }]
    neo4j_cm = _patch_neo4j_session(seed_rows, expanded_rows)
    pg_cm = _patch_pg_session()

    with patch("kg.graph_rag.kg_session", return_value=neo4j_cm), \
         patch("kg.graph_rag.async_session", return_value=pg_cm):
        result = await rag.generate_with_context("test", user_id=1)

    expanded_ids = {n.id for n in result.expanded}
    assert "def:high" in expanded_ids
    assert "def:low" not in expanded_ids


@pytest.mark.asyncio
async def test_user_state_thresholds():
    """score >= 0.8 → mastered, >= 0.5 → in_progress, else → weak。"""
    rag = _make_rag()
    seed_rows = [
        {"id": "kp:A", "name": "A", "type": "KP",
         "subject": "math-calc", "pg_kp_id": 1, "confidence": 0.9, "score": 0.9},
        {"id": "kp:B", "name": "B", "type": "KP",
         "subject": "math-calc", "pg_kp_id": 2, "confidence": 0.9, "score": 0.9},
        {"id": "kp:C", "name": "C", "type": "KP",
         "subject": "math-calc", "pg_kp_id": 3, "confidence": 0.9, "score": 0.9},
    ]
    mastery_rows = [
        MagicMock(kp_id=1, score=0.85, correct_count=10, total_count=12),
        MagicMock(kp_id=2, score=0.6, correct_count=6, total_count=10),
        MagicMock(kp_id=3, score=0.2, correct_count=2, total_count=10),
    ]
    neo4j_cm = _patch_neo4j_session(seed_rows, [])
    pg_cm = _patch_pg_session(mastery_rows=mastery_rows)

    with patch("kg.graph_rag.kg_session", return_value=neo4j_cm), \
         patch("kg.graph_rag.async_session", return_value=pg_cm):
        result = await rag.generate_with_context("test", user_id=1)

    statuses = {n.id: n.mastery["status"] for n in result.seeds if n.mastery}
    assert statuses["kp:A"] == "mastered"
    assert statuses["kp:B"] == "in_progress"
    assert statuses["kp:C"] == "weak"


@pytest.mark.asyncio
async def test_llm_error_yields_fallback_result():
    """LLM 抛 LLMError → 仍然返回 GraphRAGResult 但 fallback=True。"""
    from kg.llm_client import LLMError

    async def boom(_prompt):
        raise LLMError("rate limit")

    rag = GraphRAG(
        embedding_model="test",
        embedding_dim=4,
        llm_call=boom,
        embed_call=_fake_embed(),
    )
    seed_rows = [
        {"id": "kp:A", "name": "A", "type": "KP",
         "subject": "math-calc", "pg_kp_id": None,
         "confidence": 0.9, "score": 0.9},
    ]
    neo4j_cm = _patch_neo4j_session(seed_rows, [])
    pg_cm = _patch_pg_session()

    with patch("kg.graph_rag.kg_session", return_value=neo4j_cm), \
         patch("kg.graph_rag.async_session", return_value=pg_cm):
        result = await rag.generate_with_context("q", user_id=1)

    assert result.fallback is True
    assert result.answer == "（AI 服务暂时不可用）"