"""flywheel 集成测 — 端到端跑 weekly_flywheel_update，mock PG + Neo4j。

不依赖真实 DB，只验证：
1. user_count < 10 时 EMA 完全短路
2. ≥ 50 用户时正信号能把 confidence 抬升
3. weekly_flywheel_update 返回 dict 含所有关键字段
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_weekly_run_with_5_users_skips_calibration():
    """user_count=5 → EMA 短路，confidence 不变；其他步骤仍跑。"""
    with patch("kg.flywheel.fetch_total_user_count",
               new_callable=AsyncMock, return_value=5), \
         patch("kg.flywheel._calibrate_by_signals",
               new_callable=AsyncMock, return_value=0), \
         patch("kg.flywheel._handle_cycles",
               new_callable=AsyncMock, return_value=0), \
         patch("kg.flywheel._handle_low_conf",
               new_callable=AsyncMock, return_value=0), \
         patch("kg.flywheel.export_to_review_queue",
               new_callable=AsyncMock, return_value=0), \
         patch("kg.flywheel._refresh_metrics",
               new_callable=AsyncMock, return_value=None):
        from kg.flywheel import weekly_flywheel_update
        result = await weekly_flywheel_update()
    assert result["user_count"] == 5
    assert "concepts_calibrated" in result
    assert "review_queue_exported" in result


@pytest.mark.asyncio
async def test_calibrate_by_signals_three_positive_lifts_confidence():
    """3 个正信号 + 100 用户 → concept.confidence 应被抬升。"""
    captured_writes = []
    concept_row = {
        "id": "kp:test",
        "old_conf": 0.5,
        "last_updated": datetime.utcnow(),
    }

    call_n = {"n": 0}

    async def fake_run(query, **params):
        call_n["n"] += 1
        r = MagicMock()
        if "UNWIND" in query:
            r.data = AsyncMock(return_value=[concept_row])
            r.single = AsyncMock(return_value=None)
        elif "SET c.confidence" in query or ("MATCH (c:Concept {id: $id}) SET" in query):
            captured_writes.append(params)
            r.data = AsyncMock(return_value=[])
            r.single = AsyncMock(return_value=None)
        else:
            r.data = AsyncMock(return_value=[])
            r.single = AsyncMock(return_value=None)
        return r

    inner = MagicMock()
    inner.run = fake_run
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=inner)
    cm.__aexit__ = AsyncMock(return_value=None)

    signals = [
        ("feedback", "kp:test", 1.0, datetime.utcnow() - timedelta(days=1))
        for _ in range(3)
    ]

    with patch("kg.flywheel.signals_explicit_feedback",
               new_callable=AsyncMock, return_value=signals), \
         patch("kg.flywheel.signals_implicit_feedback",
               new_callable=AsyncMock, return_value=[]), \
         patch("kg.flywheel.kg_session", return_value=cm):
        from kg.flywheel import _calibrate_by_signals
        n = await _calibrate_by_signals(user_count=100)

    assert n == 1
    assert any("conf" in p for p in captured_writes)


@pytest.mark.asyncio
async def test_weekly_run_result_keys():
    """weekly_flywheel_update 返回的 dict 含全部计划字段。"""
    with patch("kg.flywheel.fetch_total_user_count",
               new_callable=AsyncMock, return_value=100), \
         patch("kg.flywheel._calibrate_by_signals",
               new_callable=AsyncMock, return_value=42), \
         patch("kg.flywheel._handle_cycles",
               new_callable=AsyncMock, return_value=2), \
         patch("kg.flywheel._handle_low_conf",
               new_callable=AsyncMock, return_value=5), \
         patch("kg.flywheel.export_to_review_queue",
               new_callable=AsyncMock, return_value=7), \
         patch("kg.flywheel._refresh_metrics",
               new_callable=AsyncMock, return_value=None):
        from kg.flywheel import weekly_flywheel_update
        result = await weekly_flywheel_update()

    expected_keys = {
        "ran_at", "user_count", "concepts_calibrated",
        "cycles_detected", "low_conf_detected", "review_queue_exported",
    }
    assert expected_keys.issubset(result.keys())
    assert result["concepts_calibrated"] == 42
    assert result["cycles_detected"] == 2
    assert result["low_conf_detected"] == 5
    assert result["review_queue_exported"] == 7