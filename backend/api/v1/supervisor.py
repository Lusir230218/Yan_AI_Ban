"""Supervisor API — 统一对话入口"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from models.user import User
from agents.supervisor import run_supervisor

logger = logging.getLogger("supervisor_api")

router = APIRouter(tags=["supervisor"])


class SupervisorChatRequest(BaseModel):
    user_input: str


@router.post("/supervisor/chat")
async def supervisor_chat(
    body: SupervisorChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """统一对话入口 — 自动识别意图并路由到对应 Agent"""
    logger.info(f"supervisor_chat — user_id={current_user.id}")

    diagnosis = {
        "target_school": current_user.target_school,
        "target_major": current_user.target_major,
        "current_level": current_user.current_level,
        "learning_style": current_user.learning_style,
        "nickname": current_user.nickname,
    }

    result = await run_supervisor(
        {
            "user_id": current_user.id,
            "user_input": body.user_input,
            "diagnosis": diagnosis,
        },
        db=db,
    )

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    return result
