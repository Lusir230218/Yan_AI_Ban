"""/api/v1/analytics/* 4 个端点集成测试"""
import pytest


@pytest.mark.asyncio
async def test_user_mastery_empty(auth_client):
    """新用户没数据时返回空 dict。"""
    resp = await auth_client.get("/api/v1/analytics/user-mastery")
    assert resp.status_code == 200
    assert resp.json() == {}


@pytest.mark.asyncio
async def test_user_mastery_returns_grouped(
    auth_client, test_user, test_question, test_kp, db
):
    """答一题后应返回按学科分组的 KP 列表。"""
    await auth_client.post(
        f"/api/v1/questions/{test_question.id}/submit",
        json={"answer": "A", "subject": "数学"},
    )
    resp = await auth_client.get("/api/v1/analytics/user-mastery")
    assert resp.status_code == 200
    data = resp.json()
    assert "数学" in data
    items = data["数学"]
    assert any(k["kp_id"] == test_kp.id for k in items)
    kp_data = next(k for k in items if k["kp_id"] == test_kp.id)
    assert kp_data["score"] >= 0.0
    assert kp_data["chapter"] == "测试章节"


@pytest.mark.asyncio
async def test_weak_points_after_wrong_answer(
    auth_client, test_user, test_question, test_kp, db
):
    """答错一次 + 错因 → /weak-points 应返回该 KP + top_mistakes。"""
    await auth_client.post(
        f"/api/v1/questions/{test_question.id}/submit",
        json={"answer": "Z", "subject": "数学", "error_category": "换元忘回代"},
    )
    resp = await auth_client.get("/api/v1/analytics/weak-points?limit=5")
    assert resp.status_code == 200
    items = resp.json()
    assert any(w["kp_id"] == test_kp.id for w in items)
    wp = next(w for w in items if w["kp_id"] == test_kp.id)
    assert wp["error_count"] == 1
    assert any(m["name"] == "换元忘回代" for m in wp["top_mistakes"])


@pytest.mark.asyncio
async def test_mistake_summary(auth_client, test_user, test_question, test_kp, db):
    """答错 + 错因 → /mistake-summary 返回该错因。"""
    await auth_client.post(
        f"/api/v1/questions/{test_question.id}/submit",
        json={"answer": "Z", "subject": "数学", "error_category": "符号错"},
    )
    resp = await auth_client.get("/api/v1/analytics/mistake-summary")
    assert resp.status_code == 200
    items = resp.json()
    assert any(m["mistake_name"] == "符号错" for m in items)
    assert next(m for m in items if m["mistake_name"] == "符号错")["times"] == 1


@pytest.mark.asyncio
async def test_mistake_summary_filter_by_subject(
    auth_client, test_user, test_question, test_kp, db
):
    """按学科过滤 /mistake-summary?subject=数学。"""
    await auth_client.post(
        f"/api/v1/questions/{test_question.id}/submit",
        json={"answer": "Z", "subject": "数学", "error_category": "审题错"},
    )
    resp = await auth_client.get("/api/v1/analytics/mistake-summary?subject=数学")
    assert resp.status_code == 200
    items = resp.json()
    assert any(m["mistake_name"] == "审题错" for m in items)


@pytest.mark.asyncio
async def test_mastery_timeline_empty(auth_client, test_user, test_kp, db):
    """从未跑过 snapshot 时返回空数组（不是 500）。"""
    resp = await auth_client.get(
        f"/api/v1/analytics/mastery-timeline?kp_id={test_kp.id}&days=30"
    )
    assert resp.status_code == 200
    assert resp.json() == []
