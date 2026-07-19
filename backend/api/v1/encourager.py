"""Encourager API — 个性化学习鼓励 + 每日打卡"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from models.user import User
from agents.encourager_agent import run_encourager

logger = logging.getLogger("encourager_api")

router = APIRouter(tags=["encourager"])


@router.get("/encourager/message")
async def get_encourage_message(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前鼓励消息"""
    logger.info(f"get_encourage_message — user_id={current_user.id}")

    diagnosis = {
        "target_school": current_user.target_school,
        "target_major": current_user.target_major,
        "current_level": current_user.current_level,
    }

    result = await run_encourager(
        {
            "user_id": current_user.id,
            "nickname": current_user.nickname or "同学",
            "diagnosis": diagnosis,
        },
        db=db,
    )

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    return {
        "message": result.get("message", ""),
        "message_type": result.get("message_type", "daily"),
        "streak_days": result.get("streak_days", 0),
        "today_count": result.get("today_count", 0),
    }


@router.post("/encourager/checkin")
async def daily_checkin(
    current_user: User = Depends(get_current_user),
):
    """每日打卡"""
    logger.info(f"daily_checkin — user_id={current_user.id}")
    return {
        "message": f"打卡成功！{current_user.nickname or '同学'}，继续保持！",
        "checked_in": True,
    }
