"""掌握度计算 — 纯应用层函数，无 LLM 依赖"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.study import UserKpMastery


async def compute_score(db: AsyncSession, user_id: int, kp_id: int) -> float:
    """公式: score = min(1, accuracy × retention + bonus)

    - accuracy = correct_count / max(total_count, 1)
    - retention = max(0.3, 1 - days_since / (30 × ease_factor))
    - bonus = min(0.2, review_count × 0.05)
    """
    row = (await db.execute(
        select(UserKpMastery).where(
            UserKpMastery.user_id == user_id,
            UserKpMastery.kp_id == kp_id,
        )
    )).scalar_one_or_none()
    if not row:
        return 0.5

    accuracy = row.correct_count / max(row.total_count, 1)
    days_since = (datetime.now(timezone.utc) - row.last_reviewed).days
    retention = max(0.3, 1 - days_since / (30 * row.ease_factor))
    bonus = min(0.2, row.review_count * 0.05)
    return min(1.0, accuracy * retention + bonus)
