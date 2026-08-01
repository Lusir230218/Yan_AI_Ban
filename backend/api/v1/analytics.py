"""阶段二 v3 用户状态分析 API"""
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from models.user import User

router = APIRouter()


@router.get("/user-mastery")
async def user_mastery(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(text("""
        SELECT kp.subject, kp.id AS kp_id, kp.name, kp.code, kp.level,
               kp.chapter, kp.section, m.score, m.correct_count, m.total_count,
               m.last_reviewed
        FROM user_kp_mastery m
        JOIN knowledge_points kp ON m.kp_id = kp.id
        WHERE m.user_id = :uid
        ORDER BY kp.subject, kp.sort_order
    """), {"uid": current_user.id})).mappings().all()

    by_subject: dict[str, list] = defaultdict(list)
    for r in rows:
        by_subject[r["subject"]].append({
            "kp_id": r["kp_id"], "name": r["name"], "code": r["code"],
            "level": r["level"], "chapter": r["chapter"], "section": r["section"],
            "score": float(r["score"]),
            "correct_rate": r["correct_count"] / max(r["total_count"], 1),
            "last_reviewed": r["last_reviewed"].isoformat() if r["last_reviewed"] else None,
        })
    return dict(by_subject)


@router.get("/weak-points")
async def weak_points(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(text("""
        SELECT kp.id AS kp_id, kp.name, kp.code, kp.subject, kp.chapter, kp.section,
               kp.difficulty, w.error_count, w.last_error_at,
               m.score AS mastery_score
        FROM user_kp_weak w
        JOIN knowledge_points kp ON w.kp_id = kp.id
        LEFT JOIN user_kp_mastery m
          ON m.user_id = w.user_id AND m.kp_id = w.kp_id
        WHERE w.user_id = :uid
        ORDER BY w.error_count DESC,
                 CASE WHEN m.score IS NULL THEN 1.0 ELSE m.score END ASC
        LIMIT :limit
    """), {"uid": current_user.id, "limit": limit})).mappings().all()

    result = []
    for r in rows:
        top_mistakes = (await db.execute(text("""
            SELECT m.name AS mistake, um.times,
                   COALESCE(moi.count, 0) AS kp_count
            FROM user_mistakes um
            JOIN mistake_categories m ON m.name = um.mistake_name
            LEFT JOIN mistake_occurs_in moi
              ON moi.mistake_name = um.mistake_name AND moi.kp_id = :kid
            WHERE um.user_id = :uid
            ORDER BY um.times DESC LIMIT 3
        """), {"uid": current_user.id, "kid": r["kp_id"]})).mappings().all()
        result.append({
            "kp_id": r["kp_id"], "name": r["name"], "code": r["code"],
            "subject": r["subject"], "chapter": r["chapter"], "section": r["section"],
            "difficulty": r["difficulty"],
            "error_count": r["error_count"],
            "last_error_at": r["last_error_at"].isoformat() if r["last_error_at"] else None,
            "mastery_score": float(r["mastery_score"]) if r["mastery_score"] is not None else None,
            "top_mistakes": [
                {"name": m["mistake"], "times": m["times"], "kp_count": m["kp_count"]}
                for m in top_mistakes
            ],
        })
    return result


@router.get("/mastery-timeline")
async def mastery_timeline(
    kp_id: int = Query(...),
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(text("""
        SELECT captured_at, score, delta
        FROM mastery_snapshots
        WHERE user_id = :uid AND kp_id = :kid
          AND captured_at > now() - make_interval(days => :days)
        ORDER BY captured_at
    """), {"uid": current_user.id, "kid": kp_id, "days": days})).mappings().all()
    return [
        {
            "captured_at": r["captured_at"].isoformat(),
            "score": float(r["score"]),
            "delta": float(r["delta"]) if r["delta"] is not None else None,
        }
        for r in rows
    ]


@router.get("/mistake-summary")
async def mistake_summary(
    subject: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if subject:
        rows = (await db.execute(text("""
            SELECT um.mistake_name, um.times, um.first_at, um.last_at,
                   COUNT(DISTINCT moi.kp_id) AS kp_count
            FROM user_mistakes um
            LEFT JOIN mistake_occurs_in moi ON moi.mistake_name = um.mistake_name
            LEFT JOIN knowledge_points kp ON kp.id = moi.kp_id
            WHERE um.user_id = :uid
              AND (kp.subject = :subj OR kp.id IS NULL)
            GROUP BY um.mistake_name, um.times, um.first_at, um.last_at
            ORDER BY um.times DESC LIMIT 20
        """), {"uid": current_user.id, "subj": subject})).mappings().all()
    else:
        rows = (await db.execute(text("""
            SELECT mistake_name, times, first_at, last_at,
                   0 AS kp_count
            FROM user_mistakes
            WHERE user_id = :uid
            ORDER BY times DESC LIMIT 20
        """), {"uid": current_user.id})).mappings().all()
    return [
        {
            "mistake_name": r["mistake_name"],
            "times": r["times"],
            "first_at": r["first_at"].isoformat(),
            "last_at": r["last_at"].isoformat(),
            "kp_count": r["kp_count"],
        }
        for r in rows
    ]
