"""submit_answer 写路径集成测试 — 走 HTTP，验证 4 张表同步"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_correct_answer_updates_mastery_only(
    auth_client, test_user, test_question, test_kp, db: AsyncSession
):
    """答对：user_kp_mastery 累加，user_kp_weak 不动。"""
    resp = await auth_client.post(
        f"/api/v1/questions/{test_question.id}/submit",
        json={"answer": "A", "subject": "数学", "source": "human"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_correct"] is True
    assert body["record"]["source"] == "human"

    row = (await db.execute(text("""
        SELECT correct_count, total_count, source_primary, score
        FROM user_kp_mastery WHERE user_id = :u AND kp_id = :k
    """), {"u": test_user.id, "k": test_kp.id})).first()
    assert row is not None
    assert row.correct_count == 1
    assert row.total_count == 1
    assert row.source_primary == "human"
    assert 0.0 <= row.score <= 1.0

    weak = (await db.execute(text("""
        SELECT count(*) FROM user_kp_weak WHERE user_id = :u AND kp_id = :k
    """), {"u": test_user.id, "k": test_kp.id})).scalar()
    assert weak == 0, "答对时不应写 user_kp_weak"


@pytest.mark.asyncio
async def test_wrong_answer_updates_weak_and_mistake(
    auth_client, test_user, test_question, test_kp, db: AsyncSession
):
    """答错 + 错因：user_kp_weak + user_mistakes + mistake_occurs_in 同步写。"""
    resp = await auth_client.post(
        f"/api/v1/questions/{test_question.id}/submit",
        json={"answer": "Z", "subject": "数学",
              "error_category": "  公式记错  ", "source": "human"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_correct"] is False
    # 错因 trim 过
    assert body["record"]["error_category"] == "公式记错"

    weak = (await db.execute(text("""
        SELECT error_count FROM user_kp_weak WHERE user_id=:u AND kp_id=:k
    """), {"u": test_user.id, "k": test_kp.id})).first()
    assert weak.error_count == 1

    cat = (await db.execute(text("""
        SELECT count(*) FROM mistake_categories WHERE name = '公式记错'
    """),)).scalar()
    assert cat == 1

    um = (await db.execute(text("""
        SELECT times FROM user_mistakes WHERE user_id=:u AND mistake_name='公式记错'
    """), {"u": test_user.id})).first()
    assert um.times == 1

    moi = (await db.execute(text("""
        SELECT count FROM mistake_occurs_in
        WHERE mistake_name='公式记错' AND kp_id=:k
    """), {"k": test_kp.id})).first()
    assert moi.count == 1


@pytest.mark.asyncio
async def test_error_category_truncated_to_64(
    auth_client, test_user, test_question, db: AsyncSession
):
    """error_category > 64 字符应截断。"""
    long_cat = "错因" * 50  # 100 字符
    resp = await auth_client.post(
        f"/api/v1/questions/{test_question.id}/submit",
        json={"answer": "Z", "subject": "数学", "error_category": long_cat},
    )
    assert resp.status_code == 200
    row = (await db.execute(text("""
        SELECT error_category FROM study_records WHERE user_id=:u ORDER BY id DESC LIMIT 1
    """), {"u": test_user.id})).first()
    assert len(row.error_category) == 64


@pytest.mark.asyncio
async def test_multiple_answers_accumulate(
    auth_client, test_user, test_question, test_kp, db: AsyncSession
):
    """连续 3 次答对 → correct_count=3, total_count=3。"""
    for _ in range(3):
        resp = await auth_client.post(
            f"/api/v1/questions/{test_question.id}/submit",
            json={"answer": "A", "subject": "数学"},
        )
        assert resp.status_code == 200

    row = (await db.execute(text("""
        SELECT correct_count, total_count FROM user_kp_mastery
        WHERE user_id=:u AND kp_id=:k
    """), {"u": test_user.id, "k": test_kp.id})).first()
    assert row.correct_count == 3
    assert row.total_count == 3


@pytest.mark.asyncio
async def test_source_primary_human_not_overwritten_by_ai(
    auth_client, test_user, test_question, test_kp, db: AsyncSession
):
    """source='human' 写入后，再以 'ai' 答不应覆盖。"""
    await auth_client.post(
        f"/api/v1/questions/{test_question.id}/submit",
        json={"answer": "A", "subject": "数学", "source": "human"},
    )
    await auth_client.post(
        f"/api/v1/questions/{test_question.id}/submit",
        json={"answer": "A", "subject": "数学", "source": "ai"},
    )
    row = (await db.execute(text("""
        SELECT source_primary FROM user_kp_mastery WHERE user_id=:u AND kp_id=:k
    """), {"u": test_user.id, "k": test_kp.id})).first()
    assert row.source_primary == "human"
