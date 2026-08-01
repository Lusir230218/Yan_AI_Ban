"""compute_score() 单元测试 — 不依赖 LLM，纯数学公式"""
from datetime import datetime, timedelta, timezone

import pytest

from models.study import UserKpMastery
from services.mastery_calc import compute_score


async def _seed_mastery(
    db, user_id: int, kp_id: int,
    correct: int, total: int, days_ago: int, review_count: int,
    ease: float = 2.5,
):
    """直接写一行 user_kp_mastery，不走 submit_answer。"""
    obj = UserKpMastery(
        user_id=user_id, kp_id=kp_id,
        correct_count=correct, total_count=total,
        last_reviewed=datetime.now(timezone.utc) - timedelta(days=days_ago),
        review_count=review_count, ease_factor=ease,
        score=0.5,
    )
    db.add(obj)
    await db.commit()


@pytest.mark.asyncio
async def test_no_record_returns_default(test_kp, test_user, db):
    """没有 mastery 行时 score = 0.5（默认值）。"""
    score = await compute_score(db, test_user.id, test_kp.id)
    assert score == 0.5


@pytest.mark.asyncio
async def test_full_accuracy_recent(test_kp, test_user, db):
    """刚答对 1 题、0 天前复习 → score 接近 1.0。"""
    await _seed_mastery(db, test_user.id, test_kp.id,
                        correct=1, total=1, days_ago=0, review_count=1)
    score = await compute_score(db, test_user.id, test_kp.id)
    # accuracy=1.0, retention=1.0, bonus=0.05 → clamp 1.0
    assert 0.95 <= score <= 1.0


@pytest.mark.asyncio
async def test_zero_accuracy(test_kp, test_user, db):
    """全错：correct=0 → accuracy=0，score 应很低。"""
    await _seed_mastery(db, test_user.id, test_kp.id,
                        correct=0, total=5, days_ago=0, review_count=1)
    score = await compute_score(db, test_user.id, test_kp.id)
    # accuracy=0, retention=1.0, bonus=0.05 → 0.05
    assert score == pytest.approx(0.05, abs=0.01)


@pytest.mark.asyncio
async def test_long_decay_floor(test_kp, test_user, db):
    """很久没复习：retention 衰减到下限 0.3。"""
    await _seed_mastery(db, test_user.id, test_kp.id,
                        correct=5, total=5, days_ago=200, review_count=1, ease=2.5)
    score = await compute_score(db, test_user.id, test_kp.id)
    # accuracy=1.0, retention=0.3 (floor), bonus=0.05 → 0.35
    assert score == pytest.approx(0.35, abs=0.01)


@pytest.mark.asyncio
async def test_review_bonus_capped(test_kp, test_user, db):
    """复习 100 次，bonus 上限 0.2。"""
    await _seed_mastery(db, test_user.id, test_kp.id,
                        correct=10, total=10, days_ago=0, review_count=100)
    score = await compute_score(db, test_user.id, test_kp.id)
    # bonus=min(0.2, 5.0)=0.2 → 1.0 * 1.0 + 0.2 = 1.2 → clamp 1.0
    assert score == pytest.approx(1.0, abs=0.01)


@pytest.mark.asyncio
async def test_score_clamped_to_1(test_kp, test_user, db):
    """任何情况 score ≤ 1.0。"""
    await _seed_mastery(db, test_user.id, test_kp.id,
                        correct=10, total=10, days_ago=0, review_count=5)
    score = await compute_score(db, test_user.id, test_kp.id)
    assert 0.0 <= score <= 1.0
