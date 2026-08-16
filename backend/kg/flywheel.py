"""阶段五·2D 飞轮：周级批跑主流程。

weekly_flywheel_update() 干 4 件事：
1. 读最近 7 天反馈 → EMA 校准每个被引 concept 的 confidence
2. 检测同类型双向 cycle → 标记 disputed
3. 检测长期低 confidence 关系 → 标记 disputed
4. 把所有 disputed 关系导出到 kg_extraction_candidates（admin review queue）

每一步都更新 Prometheus 指标，结束后返回 dict 摘要给 scheduler / admin UI。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from kg.dispute import (
    detect_cycles,
    detect_low_confidence,
    export_to_review_queue,
    mark_disputed,
    _mark_cycle_rel_ids,
)
from kg.flywheel_ema import EMAConfig, batch_update
from kg.flywheel_signals import (
    fetch_total_user_count,
    signals_explicit_feedback,
    signals_implicit_feedback,
)
from kg.metrics import (
    concepts_confidence_avg,
    disputes_exported_total,
    flywheel_runs_total,
    signals_total,
)
from kg.neo4j_client import kg_session


log = logging.getLogger(__name__)


# ============= 周级主流程 =============


async def weekly_flywheel_update() -> dict:
    """周级飞轮入口。scheduler 调用。"""
    run_start = datetime.utcnow()
    log.info("[flywheel] start at %s", run_start.isoformat())
    flywheel_runs_total.inc()

    user_count = await fetch_total_user_count()
    log.info("[flywheel] user_count=%d", user_count)

    n_calibrated = await _calibrate_by_signals(user_count)
    n_cycle = await _handle_cycles()
    n_lowconf = await _handle_low_conf()
    n_exported = await export_to_review_queue()
    disputes_exported_total.inc(n_exported)
    await _refresh_metrics()

    result = {
        "ran_at": run_start.isoformat(),
        "user_count": user_count,
        "concepts_calibrated": n_calibrated,
        "cycles_detected": n_cycle,
        "low_conf_detected": n_lowconf,
        "review_queue_exported": n_exported,
    }
    log.info("[flywheel] done: %s", result)
    return result


# ============= EMA 校准 =============


async def _calibrate_by_signals(user_count: int) -> int:
    """把显式 + 隐式反馈聚到 concept 上，跑 batch_update，更新 Neo4j confidence。"""
    since = datetime.utcnow() - timedelta(days=7)
    all_signals: list[tuple] = []
    all_signals += await signals_explicit_feedback(since)
    all_signals += await signals_implicit_feedback(since)

    # 按 concept_id 聚合
    by_concept: dict[str, list[tuple[float, datetime]]] = {}
    for kind, cid, sig, ts in all_signals:
        by_concept.setdefault(cid, []).append((sig, ts))
        signals_total.labels(kind=kind).inc()

    if not by_concept:
        log.info("[flywheel] no signals to calibrate (user_count=%d)", user_count)
        return 0

    cfg = EMAConfig()
    now = datetime.utcnow()
    calibrated = 0

    # 一次性把涉及到的 concept 的旧 confidence 拉出来，避免 N+1
    concept_ids = list(by_concept.keys())
    async with kg_session() as s:
        rows = await (await s.run("""
            UNWIND $ids AS cid
            MATCH (c:Concept {id: cid})
            RETURN c.id AS id,
                   c.confidence AS old_conf,
                   coalesce(c.updated_at, datetime()) AS last_updated
        """, ids=concept_ids)).data()

        cur_map = {r["id"]: r for r in rows}
        for cid, sigs in by_concept.items():
            row = cur_map.get(cid)
            if not row:
                continue
            old = float(row["old_conf"]) if row["old_conf"] is not None else 0.5
            # neo4j 驱动返回 neo4j.time.DateTime，不能和 Python datetime 直接相减；
            # .to_native() 转成原生 datetime；如果带 tzinfo 则抹平（now 是 naive UTC）
            last = row["last_updated"].to_native()
            if last.tzinfo is not None:
                last = last.replace(tzinfo=None)
            days_since = max((now - last).total_seconds() / 86400.0, 0.0)
            # batch_update 内部已经按时间排序；传入 user_count 控制学习率
            new = batch_update(old, sigs, now, user_count, cfg)
            await s.run("""
                MATCH (c:Concept {id: $id})
                SET c.confidence = $conf, c.updated_at = datetime()
            """, id=cid, conf=new)
            calibrated += 1
    log.info("[flywheel] calibrated %d concepts (signals=%d)",
             calibrated, len(all_signals))
    return calibrated


# ============= cycle 处理 =============


async def _handle_cycles() -> int:
    """检测同类型双向 cycle → 标记 disputed。"""
    cycles = await detect_cycles()
    if not cycles:
        return 0
    rel_ids = await _mark_cycle_rel_ids(cycles)
    return await mark_disputed(rel_ids, reason="cycle")


# ============= low confidence 处理 =============


async def _handle_low_conf() -> int:
    """长期低 confidence 关系 → 标记 disputed。"""
    rows = await detect_low_confidence()
    if not rows:
        return 0
    rel_ids = [r["rel_id"] for r in rows]
    return await mark_disputed(rel_ids, reason="low_conf")


# ============= 指标刷新 =============


async def _refresh_metrics() -> None:
    """重算平均 confidence，写入 Prometheus gauge。"""
    async with kg_session() as s:
        avg_row = await (await s.run("""
            MATCH (c:Concept)
            WHERE c.confidence IS NOT NULL
            RETURN avg(c.confidence) AS avg_conf
        """)).single()
    avg = float(avg_row["avg_conf"]) if avg_row and avg_row["avg_conf"] is not None else 0.0
    concepts_confidence_avg.set(avg)