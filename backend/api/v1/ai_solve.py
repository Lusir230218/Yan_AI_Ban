"""AI 解答 API — 支持 OCR 模式和 LLM Vision 多模态模式"""

import logging
import traceback

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from models.user import User
from agents.ai_solve_agent import run_ai_solve

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
    """AI 解答/批改题目"""
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
