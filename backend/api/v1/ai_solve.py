"""AI 解答 API — 支持 OCR 模式、LLM Vision 多模态模式、Tutor 多轮对话"""

import logging
import traceback

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.tutor import TutorSession
from agents.ai_solve_agent import run_ai_solve, run_tutor_start, run_tutor_continue, run_tutor_reveal
from schemas.tutor import TutorContinueRequest, TutorSessionResponse, TutorContinueResponse, TutorSessionListItem

logger = logging.getLogger("ai_solve")
logger.setLevel(logging.DEBUG)

router = APIRouter(tags=["AI 解答"])


@router.post("/ai-solve")
async def ai_solve(
    image: UploadFile | None = File(None, description="考题图片"),
    text: str | None = Form(None, description="直接输入的题目文本"),
    multi_modal: bool = Form(False, description="是否启用多模态模式（GPT-4o Vision）"),
    subject: str | None = Form(None, description="科目（可选）"),
    exam_variant: str | None = Form(None, description="考试变体（可选）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI 解答/批改题目（单次模式）"""
    logger.info(f"ai_solve called — multi_modal={multi_modal}, subject={subject}, has_image={image is not None}, has_text={bool(text)}")

    if not image and not text:
        raise HTTPException(status_code=400, detail="请上传图片或输入题目文本")

    image_data = None
    if image:
        try:
            image_data = await image.read()
            logger.info(f"Image received: size={len(image_data)} bytes, type={image.content_type}")
            if len(image_data) == 0:
                raise HTTPException(status_code=400, detail="上传的图片为空")
        except Exception as e:
            logger.error(f"Failed to read image: {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=400, detail=f"图片读取失败: {e}")

    try:
        result = await run_ai_solve(
            {
                "image_data": image_data,
                "raw_text": text,
                "multi_modal": multi_modal,
                "subject": subject,
                "exam_variant": exam_variant,
            },
            db=db,
            user_id=current_user.id,
        )
        logger.info(f"ai_solve result: has_question={result.get('question') is not None}, error={result.get('error')}")

        if not result.get("error"):
            await db.commit()
            logger.info("Transaction committed successfully")
    except Exception as e:
        logger.error(f"ai_solve failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"处理失败: {e}")

    if result.get("error"):
        logger.warning(f"ai_solve returned error: {result['error']}")
        raise HTTPException(status_code=500, detail=result["error"])

    return result


# ── Tutor 多轮对话端点 ──


@router.post("/ai-solve/tutor")
async def tutor_start(
    image: UploadFile | None = File(None, description="考题图片"),
    text: str | None = Form(None, description="直接输入的题目文本"),
    multi_modal: bool = Form(False, description="是否启用多模态模式"),
    subject: str | None = Form(None, description="科目（可选）"),
    exam_variant: str | None = Form(None, description="考试变体（可选）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tutor 首轮：上传题目 → 创建会话 → 返回第1层审题引导语"""
    logger.info(f"tutor_start — user_id={current_user.id}, has_image={image is not None}, has_text={bool(text)}")

    if not image and not text:
        raise HTTPException(status_code=400, detail="请上传图片或输入题目文本")

    image_data = None
    if image:
        try:
            image_data = await image.read()
            if len(image_data) == 0:
                raise HTTPException(status_code=400, detail="上传的图片为空")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"图片读取失败: {e}")

    result = await run_tutor_start(
        {
            "image_data": image_data,
            "raw_text": text,
            "multi_modal": multi_modal,
            "subject": subject,
            "exam_variant": exam_variant,
        },
        db=db,
        user_id=current_user.id,
    )

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.post("/ai-solve/tutor/{session_id}/continue")
async def tutor_continue(
    session_id: int,
    body: TutorContinueRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tutor 续接：用户回复后推进到下一轮引导"""
    logger.info(f"tutor_continue — session_id={session_id}")

    try:
        result = await run_tutor_continue(
            session_id=session_id,
            user_input=body.user_input,
            db=db,
            user_id=current_user.id,
        )
        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])
        logger.info(f"tutor_continue result: session={result.get('session_id')}, round={result.get('current_round')}, msg_len={len(result.get('message',''))}")
        return {
            "session_id": result.get("session_id"),
            "message": result.get("message"),
            "current_round": result.get("current_round"),
            "hint_level": result.get("hint_level"),
            "status": result.get("status"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"tutor_continue endpoint error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai-solve/tutor/{session_id}/reveal")
async def tutor_reveal(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tutor 索要答案：直接返回完整解析"""
    logger.info(f"tutor_reveal — session_id={session_id}")

    result = await run_tutor_reveal(
        session_id=session_id,
        db=db,
        user_id=current_user.id,
    )

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/ai-solve/tutor", response_model=list[TutorSessionListItem])
async def list_tutor_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户的所有 Tutor 会话（摘要，按最近更新倒序）"""
    result = await db.execute(
        select(TutorSession)
        .where(TutorSession.user_id == current_user.id)
        .order_by(TutorSession.updated_at.desc())
    )
    sessions = result.scalars().all()

    items = []
    for s in sessions:
        snapshot = s.question_snapshot or {}
        stem = (snapshot.get("stem") or "").strip()
        title = stem[:40] if stem else "（未识别题目）"
        items.append(TutorSessionListItem(
            id=s.id,
            question_id=s.question_id,
            current_round=s.current_round,
            hint_level=s.hint_level,
            status=s.status,
            title=title,
            message_count=len(s.messages or []),
            created_at=s.created_at,
            updated_at=s.updated_at,
        ))
    return items


@router.get("/ai-solve/tutor/{session_id}")
async def get_tutor_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询 Tutor 会话详情（对话历史 + 当前状态）"""
    result = await db.execute(select(TutorSession).where(
        TutorSession.id == session_id,
        TutorSession.user_id == current_user.id,
    ))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    return session
