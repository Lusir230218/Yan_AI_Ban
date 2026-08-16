"""阶段五·2D 飞轮：disputed 检测 + 导出。

两类争议信号：
1. cycle     — 同类型双向关系（A→B PREREQUISITE_OF + B→A 同关系 → cycle）
2. low_conf  — confidence < 阈值 且 持续 N 天未更新（视为长期低质）

注意：方案 §五提到 kg_review_queue 表，
但 2C 的 models/feedback.py 注明 "2B 已建 kg_extraction_candidates（kind=low_conf_relation）
覆盖同语义字段，本期不建新表"。所以导出写 kg_extraction_candidates，
与 2B 的 low_conf_relation kind 共用一张表，admin 端点统一读取。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import text

from core.database import async_session
from kg.neo4j_client import kg_session


# 持续 N 天未更新的低 confidence 才算"长期低质"（默认 14 天）
LOW_CONF_OLDER_THAN_DAYS = 14


# ───────────────────────── cycle 检测 ─────────────────────────


async def detect_cycles() -> list[dict]:
    """同关系类型双向 cycle 才算。

    例：PREREQUISITE_OF A→B + PREREQUISITE_OF B→A → cycle（标记两条）
    反例：A→B PREREQUISITE_OF + B→A USED_IN → 不算（合法不同关系）
    """
    async with kg_session() as s:
        rows = await (await s.run("""
            MATCH (a:Concept)-[r1:PREREQUISITE_OF]->(b:Concept)
            MATCH (b)-[r2:PREREQUISITE_OF]->(a)
            RETURN a.id AS a_id, a.name AS a_name,
                   b.id AS b_id, b.name AS b_name,
                   r1.confidence AS r1_conf,
                   r2.confidence AS r2_conf
        """)).data()
    return rows


async def _mark_cycle_rel_ids(cycles: list[dict]) -> list[str]:
    """对每对 cycle 取两条 rel 的 Neo4j elementId。"""
    if not cycles:
        return []
    out: list[str] = []
    async with kg_session() as s:
        for c in cycles:
            row = await (await s.run("""
                MATCH (a:Concept {id:$a})-[r1:PREREQUISITE_OF]->(b:Concept {id:$b})
                MATCH (b)-[r2:PREREQUISITE_OF]->(a)
                RETURN elementId(r1) AS id1, elementId(r2) AS id2
            """, a=c["a_id"], b=c["b_id"])).single()
            if row:
                out.append(row["id1"])
                out.append(row["id2"])
    return out


# ───────────────────────── low confidence 检测 ─────────────────────────


async def detect_low_confidence(
    threshold: float = 0.3,
    older_than_days: int = LOW_CONF_OLDER_THAN_DAYS,
) -> list[dict]:
    """confidence < threshold 且 updated_at < (now - older_than_days) 的关系。"""
    cutoff = datetime.utcnow() - timedelta(days=older_than_days)
    async with kg_session() as s:
        rows = await (await s.run("""
            MATCH ()-[r]->()
            WHERE r.confidence < $thr
              AND r.updated_at < $cutoff
              AND coalesce(r.disputed, false) = false
            RETURN elementId(r) AS rel_id, r.confidence AS conf,
                   startNode(r).id AS from_id,
                   coalesce(startNode(r).name, '?') AS from_name,
                   type(r) AS rel,
                   endNode(r).id AS to_id,
                   coalesce(endNode(r).name, '?') AS to_name
        """, thr=threshold, cutoff=cutoff)).data()
    return rows


# ───────────────────────── 标记 disputed ─────────────────────────


async def mark_disputed(rel_ids: list[str], reason: str) -> int:
    """在 Neo4j 上把关系打 disputed 标记 + 记录原因。"""
    if not rel_ids:
        return 0
    async with kg_session() as s:
        await s.run("""
            MATCH ()-[r]->()
            WHERE elementId(r) IN $ids
            SET r.disputed = true,
                r.disputed_at = datetime(),
                r.disputed_reason = $reason
        """, ids=rel_ids, reason=reason)
    return len(rel_ids)


# ───────────────────────── 导出到 admin review queue ─────────────────────────


async def export_to_review_queue() -> int:
    """把 Neo4j 中所有 disputed=true 的关系同步进 kg_extraction_candidates。

    Returns: 新写入的候选数。

    写入前先清掉旧的低 conf / cycle 候选（防止重复堆积），
    kg_extraction_candidates.status 字段承担 review queue 状态机：
    pending（待审）→ approved / rejected（人工决定）。
    """
    async with kg_session() as s:
        rows = await (await s.run("""
            MATCH ()-[r]->()
            WHERE coalesce(r.disputed, false) = true
            RETURN startNode(r).id AS from_id,
                   coalesce(startNode(r).name, '?') AS from_name,
                   type(r) AS rel,
                   r.confidence AS conf,
                   coalesce(r.disputed_reason, 'unknown') AS reason,
                   endNode(r).id AS to_id,
                   coalesce(endNode(r).name, '?') AS to_name
        """)).data()

    async with async_session() as db:
        # 清掉旧 cycle / low_conf 候选（同 kind 幂等重导）
        await db.execute(text("""
            DELETE FROM kg_extraction_candidates
            WHERE kind IN ('cycle', 'low_conf_relation')
              AND status = 'pending'
        """))
        for r in rows:
            payload = {
                "from_id":   r["from_id"],
                "from_name": r["from_name"],
                "rel":       r["rel"],
                "conf":      float(r["conf"]) if r["conf"] is not None else 0.0,
                "reason":    r["reason"],
                "to_id":     r["to_id"],
                "to_name":   r["to_name"],
            }
            # plan §五 reason 字段语义对齐：cycle → 'cycle'，low_conf → 'low_conf_relation'
            kind = "cycle" if r["reason"] == "cycle" else "low_conf_relation"
            await db.execute(text("""
                INSERT INTO kg_extraction_candidates
                    (kind, payload, status, created_at)
                VALUES
                    (:kind, CAST(:payload AS JSONB), 'pending', now())
            """), {
                "kind": kind,
                "payload": json.dumps(payload, ensure_ascii=False),
            })
        await db.commit()
    return len(rows)