"""测试 record_user_state helper + AI 辅导路径自动填错因"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.user_state import record_user_state


@pytest.mark.asyncio
async def test_record_user_state_wrong_with_error_category(
    test_user, test_kp, db: AsyncSession
):
    """helper 单元测试：答错 + error_category → 4 张表同步。"""
    record = await record_user_state(
        db,
        user_id=test_user.id,
        kp_id=test_kp.id,
        is_correct=False,
        error_category="换元忘回代",
        source="ai",
        subject="数学",
    )
    await db.commit()

    assert record.error_category == "换元忘回代"
    assert record.source == "ai"

    weak = (await db.execute(text("""
        SELECT error_count FROM user_kp_weak
        WHERE user_id=:u AND kp_id=:k
    """), {"u": test_user.id, "k": test_kp.id})).first()
    assert weak.error_count == 1

    um = (await db.execute(text("""
        SELECT times FROM user_mistakes
        WHERE user_id=:u AND mistake_name='换元忘回代'
    """), {"u": test_user.id})).first()
    assert um.times == 1


@pytest.mark.asyncio
async def test_record_user_state_error_category_trimmed(
    test_user, test_kp, db: AsyncSession
):
    """error_category 前后空格被 strip，超 64 截断。"""
    record = await record_user_state(
        db,
        user_id=test_user.id,
        kp_id=test_kp.id,
        is_correct=False,
        error_category="  换元忘回代  ",
    )
    await db.commit()
    assert record.error_category == "换元忘回代"

    long_cat = "错" * 100
    record2 = await record_user_state(
        db,
        user_id=test_user.id,
        kp_id=test_kp.id,
        is_correct=False,
        error_category=long_cat,
    )
    await db.commit()
    assert len(record2.error_category) == 64


@pytest.mark.asyncio
async def test_record_user_state_correct_no_mistake(
    test_user, test_kp, db: AsyncSession
):
    """答对时不写 user_kp_weak / mistake_*。"""
    await record_user_state(
        db,
        user_id=test_user.id,
        kp_id=test_kp.id,
        is_correct=True,
        error_category="不应该被记录",
    )
    await db.commit()

    weak = (await db.execute(text("""
        SELECT count(*) FROM user_kp_weak WHERE user_id=:u AND kp_id=:k
    """), {"u": test_user.id, "k": test_kp.id})).scalar()
    assert weak == 0

    um = (await db.execute(text("""
        SELECT count(*) FROM user_mistakes WHERE user_id=:u
    """), {"u": test_user.id})).scalar()
    assert um == 0


@pytest.mark.asyncio
async def test_ai_solve_save_result_writes_error_category(
    test_user, test_kp, db: AsyncSession
):
    """AI 辅导的 save_result：LLM errors[0] 落到 user_mistakes。"""
    from agents.ai_solve_agent import save_result

    state = {
        "_db_session": db,
        "created_by": test_user.id,
        "stem": f"测试题-{test_user.id}-AI-1",
        "subject": "数学",
        "question_type": "choice",
        "options": "[]",
        "correct_answer": "A",
        "knowledge_point_id": test_kp.id,
        "is_correct": False,
        "errors": ["换元忘回代", "积分常数漏了"],
        "explanation": "...",
    }
    result = await save_result(state)
    await db.commit()

    assert "error" not in result, result.get("error")

    um = (await db.execute(text("""
        SELECT times FROM user_mistakes
        WHERE user_id=:u AND mistake_name='换元忘回代'
    """), {"u": test_user.id})).first()
    assert um is not None
    assert um.times == 1


@pytest.mark.asyncio
async def test_ai_solve_save_result_correct_no_mistake(
    test_user, test_kp, db: AsyncSession
):
    """AI 答对时不写 user_mistakes。"""
    from agents.ai_solve_agent import save_result

    state = {
        "_db_session": db,
        "created_by": test_user.id,
        "stem": f"测试题-{test_user.id}-AI-2",
        "subject": "数学",
        "question_type": "choice",
        "options": "[]",
        "correct_answer": "A",
        "knowledge_point_id": test_kp.id,
        "is_correct": True,
        "errors": [],
        "explanation": "...",
    }
    result = await save_result(state)
    await db.commit()
    assert "error" not in result

    um = (await db.execute(text("""
        SELECT count(*) FROM user_mistakes WHERE user_id=:u
    """), {"u": test_user.id})).scalar()
    assert um == 0
