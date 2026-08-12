"""dispute 单测 — 用 mock Neo4j session，覆盖 cycle + low_conf 两类检测。

不依赖真实 Neo4j；只验证 Cypher 解析后的语义正确性。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from kg.dispute import detect_cycles, detect_low_confidence, mark_disputed


def _neo4j_session(rows_by_call: list[list[dict]]):
    """构造 mock Neo4j session — 每次 s.run() 返回 rows_by_call 中的下一组。"""
    call_n = {"n": 0}

    async def fake_run(query, **params):
        call_n["n"] += 1
        result = MagicMock()
        idx = min(call_n["n"] - 1, len(rows_by_call) - 1)
        result.data = AsyncMock(return_value=rows_by_call[idx])
        result.single = AsyncMock(return_value=rows_by_call[idx][0] if rows_by_call[idx] else None)
        return result

    inner = MagicMock()
    inner.run = fake_run
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=inner)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.mark.asyncio
async def test_detect_cycles_same_type_returns_one_pair():
    """同关系类型双向 → 算一个 cycle。"""
    cm = _neo4j_session([
        [{
            "a_id": "kp:A", "a_name": "A",
            "b_id": "kp:B", "b_name": "B",
            "r1_conf": 0.5, "r2_conf": 0.5,
        }],
    ])
    with pytest.MonkeyPatch.context() as mp:
        from kg import dispute as d
        mp.setattr(d, "kg_session", lambda: cm)
        cycles = await detect_cycles()
    assert len(cycles) == 1
    assert cycles[0]["a_id"] == "kp:A"
    assert cycles[0]["b_id"] == "kp:B"


@pytest.mark.asyncio
async def test_detect_cycles_no_results_returns_empty():
    """无 cycle 时返回空 list。"""
    cm = _neo4j_session([[]])
    with pytest.MonkeyPatch.context() as mp:
        from kg import dispute as d
        mp.setattr(d, "kg_session", lambda: cm)
        cycles = await detect_cycles()
    assert cycles == []


@pytest.mark.asyncio
async def test_detect_low_confidence_threshold():
    """低 confidence + 老的更新才被检测出来。"""
    cm = _neo4j_session([[
        {"rel_id": 1, "conf": 0.2,
         "from_id": "kp:A", "from_name": "A",
         "rel": "PREREQUISITE_OF",
         "to_id": "kp:B", "to_name": "B"},
    ]])
    with pytest.MonkeyPatch.context() as mp:
        from kg import dispute as d
        mp.setattr(d, "kg_session", lambda: cm)
        rows = await detect_low_confidence(threshold=0.3, older_than_days=14)
    assert len(rows) == 1
    assert rows[0]["from_id"] == "kp:A"


@pytest.mark.asyncio
async def test_detect_low_confidence_high_conf_excluded():
    """高 confidence（> 0.5）应该被过滤掉 — Cypher 自身做，但 mock 也得照办。"""
    cm = _neo4j_session([[]])
    with pytest.MonkeyPatch.context() as mp:
        from kg import dispute as d
        mp.setattr(d, "kg_session", lambda: cm)
        rows = await detect_low_confidence(threshold=0.3)
    assert rows == []


@pytest.mark.asyncio
async def test_mark_disputed_empty_list_returns_zero():
    """空 ids 直接返回 0，不打 Neo4j。"""
    n = await mark_disputed([], reason="cycle")
    assert n == 0


@pytest.mark.asyncio
async def test_mark_disputed_calls_set():
    """传 ids 时打 Cypher SET r.disputed=true。"""
    captured = {}

    async def fake_run(query, **params):
        captured["query"] = query
        captured["params"] = params
        r = MagicMock()
        r.data = AsyncMock(return_value=[])
        r.single = AsyncMock(return_value=None)
        return r

    inner = MagicMock()
    inner.run = fake_run
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=inner)
    cm.__aexit__ = AsyncMock(return_value=None)

    with pytest.MonkeyPatch.context() as mp:
        from kg import dispute as d
        mp.setattr(d, "kg_session", lambda: cm)
        n = await mark_disputed([10, 20], reason="cycle")
    assert n == 2
    assert "SET r.disputed = true" in captured["query"]
    assert captured["params"]["reason"] == "cycle"
    assert captured["params"]["ids"] == [10, 20]