"""阶段五·2D 飞轮：admin 后台 API。

挂在 /kg/admin/flywheel/* 下，与 2B 的 /kg/admin/* (review-queue / approve)
并存 — 2B 的 candidates.kind 包括 chunk_seen / concept_conflict 等其他类型，
2D 只关心 cycle + low_conf_relation。

端点清单：
  GET    /kg/admin/flywheel/review-queue     待 review 的 cycle / low_conf 关系
  POST   /kg/admin/flywheel/approve-review   批准（恢复 disputed=false）
  POST   /kg/admin/flywheel/reject-review    拒绝（删除 Neo4j 关系）
  POST   /kg/admin/flywheel/merge-concepts   手工合并两个 concept
  POST   /kg/admin/flywheel/archive          归档 / 还原 concept
  GET    /kg/admin/flywheel/stats            概览指标（concepts / feedback / queue size）
  POST   /kg/admin/flywheel/run-flywheel     手动触发周级批跑（运维）
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from core.database import async_session
from core.security import get_current_user, require_admin
from kg.admin_concepts import (
    archive_concept, merge_concepts, restore_concept,
)
from kg.flywheel import weekly_flywheel_update
from kg.neo4j_client import kg_session
from models.user import User


router = APIRouter(prefix="/kg/admin/flywheel", tags=["kg_admin_flywheel"])


# ────────────────────── Pydantic 请求体 ──────────────────────


class MergeReq(BaseModel):
    keep_id: str
    drop_id: str


class ArchiveReq(BaseModel):
    concept_id: str
    restore: bool = False


class ApproveReq(BaseModel):
    queue_id: int


class RunFlywheelReq(BaseModel):
    user_count: int | None = None  # None 时让 flywheel 自己去 PG 查


# ────────────────────── review queue ──────────────────────


@router.get("/review-queue")
async def list_review_queue(
    user: User = Depends(get_current_user),
    _: User = Depends(require_admin),
):
    """返回 pending 状态的 cycle / low_conf_relation 候选。

    payload 是 JSONB 字段，2D 写入时固定包含
    {from_id, from_name, rel, conf, reason, to_id, to_name}。
    """
    async with async_session() as db:
        rows = (await db.execute(text("""
            SELECT id, kind, payload, created_at
            FROM kg_extraction_candidates
            WHERE status = 'pending'
              AND kind IN ('cycle', 'low_conf_relation')
            ORDER BY created_at DESC
            LIMIT 100
        """))).all()
    out = []
    for r in rows:
        payload = r.payload if isinstance(r.payload, dict) else {}
        out.append({
            "id": r.id,
            "kind": r.kind,
            "from_id": payload.get("from_id"),
            "from_name": payload.get("from_name"),
            "rel": payload.get("rel"),
            "conf": payload.get("conf"),
            "reason": payload.get("reason"),
            "to_id": payload.get("to_id"),
            "to_name": payload.get("to_name"),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return out


@router.post("/approve-review")
async def approve_review(
    body: ApproveReq,
    user: User = Depends(get_current_user),
    _: User = Depends(require_admin),
):
    """批准 = 把 Neo4j 关系 disputed=false，恢复显示。"""
    async with async_session() as db:
        row = (await db.execute(text("""
            SELECT id, kind, payload FROM kg_extraction_candidates
            WHERE id = :id
        """), {"id": body.queue_id})).first()
        if not row:
            raise HTTPException(404, "queue entry not found")
        payload = row.payload if isinstance(row.payload, dict) else {}
        from_id = payload.get("from_id")
        to_id = payload.get("to_id")
        rel_type = payload.get("rel")

        # 恢复 Neo4j 关系
        if from_id and to_id and rel_type:
            try:
                async with kg_session() as s:
                    await s.run(f"""
                        MATCH (a:Concept {{id:$a}})-[rel:{rel_type}]->(b:Concept {{id:$b}})
                        SET rel.disputed = false,
                            rel.disputed_at = null,
                            rel.disputed_reason = null
                    """, a=from_id, b=to_id)
            except Exception:
                # 关系可能已被外部删除；忽略错误继续清队列
                pass

        await db.execute(text("""
            UPDATE kg_extraction_candidates
            SET status = 'approved', reviewed_at = now()
            WHERE id = :id
        """), {"id": body.queue_id})
        await db.commit()
    return {"ok": True, "queue_id": body.queue_id}


@router.post("/reject-review")
async def reject_review(
    body: ApproveReq,
    user: User = Depends(get_current_user),
    _: User = Depends(require_admin),
):
    """拒绝 = 删除 Neo4j 关系 + 队列标记 rejected。"""
    async with async_session() as db:
        row = (await db.execute(text("""
            SELECT id, kind, payload FROM kg_extraction_candidates
            WHERE id = :id
        """), {"id": body.queue_id})).first()
        if not row:
            raise HTTPException(404, "queue entry not found")
        payload = row.payload if isinstance(row.payload, dict) else {}
        from_id = payload.get("from_id")
        to_id = payload.get("to_id")
        rel_type = payload.get("rel")

        if from_id and to_id and rel_type:
            try:
                async with kg_session() as s:
                    await s.run(f"""
                        MATCH (a:Concept {{id:$a}})-[rel:{rel_type}]->(b:Concept {{id:$b}})
                        DELETE rel
                    """, a=from_id, b=to_id)
            except Exception:
                pass

        await db.execute(text("""
            UPDATE kg_extraction_candidates
            SET status = 'rejected', reviewed_at = now()
            WHERE id = :id
        """), {"id": body.queue_id})
        await db.commit()
    return {"ok": True, "queue_id": body.queue_id}


# ────────────────────── 手工合并 / 归档 ──────────────────────


@router.post("/merge-concepts")
async def merge_concepts_api(
    body: MergeReq,
    user: User = Depends(get_current_user),
    _: User = Depends(require_admin),
):
    """手工合并两个 concept：所有边接到 keep，drop 删除。"""
    if body.keep_id == body.drop_id:
        raise HTTPException(400, "keep_id and drop_id must differ")
    return await merge_concepts(body.keep_id, body.drop_id, user.id)


@router.post("/archive")
async def archive_api(
    body: ArchiveReq,
    user: User = Depends(get_current_user),
    _: User = Depends(require_admin),
):
    """归档或还原。restore=true 时还原；否则归档。"""
    if body.restore:
        return await restore_concept(body.concept_id)
    return await archive_concept(body.concept_id, user.id)


# ────────────────────── 概览指标 ──────────────────────


@router.get("/stats")
async def kg_stats(
    user: User = Depends(get_current_user),
    _: User = Depends(require_admin),
):
    """概览：概念总数 / 活跃 / disputed / 归档 / 平均 confidence / 7d 反馈 / queue 大小。"""
    async with kg_session() as s:
        row = await (await s.run("""
            MATCH (c:Concept)
            RETURN
              count(c) AS total,
              count(CASE WHEN c.status = 'active'   THEN 1 END) AS active,
              count(CASE WHEN c.status = 'disputed' THEN 1 END) AS disputed,
              count(CASE WHEN c.status = 'archived' THEN 1 END) AS archived,
              avg(c.confidence) AS avg_conf
        """)).single()

    async with async_session() as db:
        fb = (await db.execute(text("""
            SELECT count(*) AS n FROM feedback_kg_answer
            WHERE created_at > now() - INTERVAL '7 days'
        """))).first()
        qr = (await db.execute(text("""
            SELECT count(*) AS n FROM kg_extraction_candidates
            WHERE status = 'pending' AND kind IN ('cycle', 'low_conf_relation')
        """))).first()

    return {
        "concepts": {
            "total":    int(row["total"])    if row else 0,
            "active":   int(row["active"])   if row else 0,
            "disputed": int(row["disputed"]) if row else 0,
            "archived": int(row["archived"]) if row else 0,
            "avg_conf": float(row["avg_conf"]) if row and row["avg_conf"] is not None else 0.0,
        },
        "feedback_7d":      int(fb[0]) if fb else 0,
        "review_queue_size": int(qr[0]) if qr else 0,
    }


# ────────────────────── 手动触发批跑 ──────────────────────


@router.post("/run-flywheel")
async def run_flywheel_endpoint(
    body: RunFlywheelReq | None = None,
    user: User = Depends(get_current_user),
    _: User = Depends(require_admin),
):
    """运维手动触发周级批跑（不等 cron）。"""
    result = await weekly_flywheel_update()
    return result