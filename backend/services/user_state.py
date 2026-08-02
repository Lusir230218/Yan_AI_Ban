"""统一用户状态写路径 — 手动答题 / AI 辅导 / 任何答题事件都走这里

写 4 张表 + score 重算（事务内）：
  study_records (事件流水)
  user_kp_mastery (物化掌握度)
  user_kp_weak (薄弱累计, 仅答错时)
  mistake_categories / user_mistakes / mistake_occurs_in (仅答错且 error_category 非空)
"""
from typing import Optional

from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.mistake import MistakeCategory, MistakeOccursIn, UserMistake
from models.study import StudyRecord, UserKpMastery, UserKpWeak
from services.mastery_calc import compute_score


async def record_user_state(
    db: AsyncSession,
    user_id: int,
    kp_id: Optional[int],
    is_correct: Optional[bool],
    *,
    error_category: Optional[str] = None,
    source: str = "human",
    subject: str = "",
    question_id: Optional[int] = None,
    duration_seconds: int = 0,
) -> StudyRecord:
    """统一写路径。返回 StudyRecord 行。"""
    if error_category:
        error_category = error_category.strip()[:64] or None

    # 1. study_records（事件流水）
    record = StudyRecord(
        user_id=user_id,
        subject=subject,
        knowledge_point_id=kp_id,
        question_id=question_id,
        is_correct=is_correct,
        duration_seconds=duration_seconds,
        error_category=error_category,
        source=source,
    )
    db.add(record)
    await db.flush()

    if kp_id is None:
        return record

    # 2. user_kp_mastery（物化）— SQLAlchemy 2.0: 类上直接 .列名
    await db.execute(
        pg_insert(UserKpMastery).values(
            user_id=user_id,
            kp_id=kp_id,
            correct_count=1 if is_correct else 0,
            total_count=1,
            last_reviewed=record.created_at,
            review_count=1,
            source_primary=source,
        ).on_conflict_do_update(
            index_elements=["user_id", "kp_id"],
            set_={
                "correct_count": UserKpMastery.correct_count + (1 if is_correct else 0),
                "total_count": UserKpMastery.total_count + 1,
                "last_reviewed": record.created_at,
                "review_count": UserKpMastery.review_count + 1,
                "source_primary": case(
                    (UserKpMastery.source_primary == "human", "human"),
                    else_=source,
                ),
            },
        )
    )

    # 3. user_kp_weak（答错时）
    if not is_correct:
        await db.execute(
            pg_insert(UserKpWeak).values(
                user_id=user_id,
                kp_id=kp_id,
                error_count=1,
                last_error_at=record.created_at,
            ).on_conflict_do_update(
                index_elements=["user_id", "kp_id"],
                set_={
                    "error_count": UserKpWeak.error_count + 1,
                    "last_error_at": record.created_at,
                },
            )
        )

    # 4. mistake_* 3 张表（答错且 error_category 非空）
    if not is_correct and error_category:
        await db.execute(
            pg_insert(MistakeCategory)
            .values(name=error_category)
            .on_conflict_do_nothing()
        )
        await db.execute(
            pg_insert(UserMistake).values(
                user_id=user_id,
                mistake_name=error_category,
                times=1,
                first_at=record.created_at,
                last_at=record.created_at,
            ).on_conflict_do_update(
                index_elements=["user_id", "mistake_name"],
                set_={
                    "times": UserMistake.times + 1,
                    "last_at": record.created_at,
                },
            )
        )
        await db.execute(
            pg_insert(MistakeOccursIn).values(
                mistake_name=error_category,
                kp_id=kp_id,
                count=1,
                last_at=record.created_at,
            ).on_conflict_do_update(
                index_elements=["mistake_name", "kp_id"],
                set_={
                    "count": MistakeOccursIn.count + 1,
                    "last_at": record.created_at,
                },
            )
        )

    # 5. score 重算
    if settings.MASTERY_RECOMPUTE_ON_ANSWER:
        score = await compute_score(db, user_id, kp_id)
        await db.execute(
            UserKpMastery.__table__.update()
            .where(UserKpMastery.user_id == user_id, UserKpMastery.kp_id == kp_id)
            .values(score=score)
        )

    return record
