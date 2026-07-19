"""Encourager Agent — 个性化学习鼓励

节点：gather_status → check_milestone → generate_message

用法：
  from agents.encourager_agent import run_encourager
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone, timedelta
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from models.study import StudyRecord, StudyPlan

logger = logging.getLogger("encourager_agent")
logger.setLevel(logging.DEBUG)


class EncouragerState(TypedDict):
    user_id: int
    nickname: str
    diagnosis: dict | None

    today_records_count: int
    streak_days: int
    recent_mood: float
    study_progress: dict

    message: str
    message_type: str                  # daily / milestone / comfort / reminder

    _db_session: AsyncSession | None

    error: str | None


async def gather_status(state: EncouragerState) -> dict:
    """查询今日学习记录、连续打卡天数、近期情绪、学习进度"""
    from core.database import async_session
    from sqlalchemy import distinct

    user_id = state.get("user_id")

    async with async_session() as session:
        today = date.today()

        # 今日记录数
        result = await session.execute(
            select(func.count(StudyRecord.id)).where(
                StudyRecord.user_id == user_id,
                cast(StudyRecord.created_at, Date) == today,
            )
        )
        today_count = result.scalar() or 0

        # 连续打卡天数（一次查询替代循环）
        result = await session.execute(
            select(distinct(cast(StudyRecord.created_at, Date)))
            .where(StudyRecord.user_id == user_id)
            .order_by(cast(StudyRecord.created_at, Date).desc())
            .limit(366)
        )
        study_dates = {row[0] for row in result.all()}

        streak_days = 0
        for i in range(366):
            check_date = today - timedelta(days=i)
            if check_date in study_dates:
                streak_days += 1
            else:
                break

        # 近期情绪
        result = await session.execute(
            select(func.avg(StudyRecord.emotion_score)).where(
                StudyRecord.user_id == user_id,
                StudyRecord.created_at >= datetime.now(timezone.utc) - timedelta(days=7),
            )
        )
        avg_mood = result.scalar() or 5.0

        # 学习进度
        result = await session.execute(
            select(StudyPlan).where(
                StudyPlan.user_id == user_id,
                StudyPlan.status == "active",
            ).limit(1)
        )
        active_plan = result.scalar_one_or_none()

        progress = {}
        if active_plan:
            total_days = (active_plan.end_date - active_plan.start_date).days or 1
            elapsed = (today - active_plan.start_date).days
            pct = min(100, max(0, round(elapsed / total_days * 100)))
            remaining = max(0, (active_plan.end_date - today).days)
            progress = {
                "phase": active_plan.phase,
                "completed_pct": pct,
                "days_remaining": remaining,
            }

    return {
        "today_records_count": today_count,
        "streak_days": streak_days,
        "recent_mood": round(avg_mood, 1),
        "study_progress": progress,
    }


async def check_milestone(state: EncouragerState) -> dict:
    """检查里程碑触发"""
    streak = state.get("streak_days", 0)
    if streak in (7, 30, 100):
        return {"message_type": "milestone"}
    return {}


async def generate_message(state: EncouragerState) -> dict:
    """根据状态生成个性化鼓励语（纯规则，不调 LLM）"""
    nickname = state.get("nickname", "同学")
    today_count = state.get("today_records_count", 0)
    streak = state.get("streak_days", 0)
    mood = state.get("recent_mood", 5.0)
    progress = state.get("study_progress", {})
    msg_type = state.get("message_type", "daily")

    hour = datetime.now().hour
    time_greeting = "早上好" if hour < 12 else "下午好" if hour < 18 else "晚上好"

    if not msg_type or msg_type == "daily":
        if today_count == 0 and hour >= 20:
            msg_type = "reminder"
        elif mood < 3.0:
            msg_type = "comfort"
        elif streak in (7, 30, 100):
            msg_type = "milestone"
        else:
            msg_type = "daily"

    messages = {
        "daily": f"{time_greeting}，{nickname}！今天已经完成了 {today_count} 道题，连续学习 {streak} 天，保持这个节奏，每一步都在靠近目标。",
        "milestone": f"连续学习 {streak} 天，{nickname}，你太棒了！这份坚持本身就是一种胜利。让好习惯继续带你前进。",
        "comfort": f"{nickname}，学习路上有起伏很正常。今天感觉累的话就早点休息，调整好状态比硬撑更重要。你已经走了很远，别否定自己。",
        "reminder": f"{time_greeting}，{nickname}～今天还没有学习记录哦。做一道题、看一个知识点都算数，保持习惯最重要！",
    }

    message = messages.get(msg_type, messages["daily"])

    if progress:
        pct = progress.get("completed_pct", 0)
        remaining = progress.get("days_remaining", 0)
        message += f" 当前{progress.get('phase', '')}阶段已完成 {pct}%，还剩 {remaining} 天，加油！"

    return {"message": message, "message_type": msg_type}


def build_encourager_graph() -> StateGraph:
    workflow = StateGraph(EncouragerState)

    workflow.add_node("gather_status", gather_status)
    workflow.add_node("check_milestone", check_milestone)
    workflow.add_node("generate_message", generate_message)

    workflow.set_entry_point("gather_status")
    workflow.add_edge("gather_status", "check_milestone")
    workflow.add_edge("check_milestone", "generate_message")
    workflow.add_edge("generate_message", END)

    return workflow


encourager_app = build_encourager_graph().compile()


class EncouragerInput(TypedDict, total=False):
    user_id: int
    nickname: str
    diagnosis: dict | None


class EncouragerOutput(TypedDict):
    message: str
    message_type: str
    streak_days: int
    today_count: int
    error: str | None


async def run_encourager(
    inputs: EncouragerInput,
    db: AsyncSession | None = None,
) -> EncouragerOutput:
    """外部入口 — 生成鼓励消息"""
    logger.info(f"run_encourager — user_id={inputs.get('user_id')}")

    initial: EncouragerState = {
        "user_id": inputs.get("user_id"),
        "nickname": inputs.get("nickname", "同学"),
        "diagnosis": inputs.get("diagnosis"),
        "today_records_count": 0,
        "streak_days": 0,
        "recent_mood": 5.0,
        "study_progress": {},
        "message": "",
        "message_type": "",
        "_db_session": db,
        "error": None,
    }

    try:
        result = await encourager_app.ainvoke(initial)
    except Exception as e:
        logger.error(f"encourager failed: {e}")
        return EncouragerOutput(message="", message_type="daily", streak_days=0, today_count=0, error=str(e))

    if result.get("error"):
        return EncouragerOutput(message="", message_type="daily", streak_days=0, today_count=0, error=result["error"])

    return EncouragerOutput(
        message=result.get("message", ""),
        message_type=result.get("message_type", "daily"),
        streak_days=result.get("streak_days", 0),
        today_count=result.get("today_records_count", 0),
        error=None,
    )
