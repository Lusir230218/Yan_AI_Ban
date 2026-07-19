"""Evaluation API — 学习评估与分数预测"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.assessment import EvaluationReport
from agents.evaluator_agent import run_evaluation

logger = logging.getLogger("evaluation_api")

router = APIRouter(tags=["evaluation"])


@router.post("/evaluation/predict")
async def predict_evaluation(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """触发分数预测 — 返回各科预测分+薄弱点+建议"""
    logger.info(f"predict_evaluation — user_id={current_user.id}")

    diagnosis = {
        "target_school": current_user.target_school,
        "target_major": current_user.target_major,
        "current_level": current_user.current_level,
        "learning_style": current_user.learning_style,
    }

    result = await run_evaluation(
        {"user_id": current_user.id, "diagnosis": diagnosis},
        db=db,
    )

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    return {
        "predicted_scores": result.get("predicted_scores", {}),
        "weak_points": result.get("weak_points", []),
        "suggestions": result.get("suggestions", []),
        "report_id": result.get("report_id"),
    }


@router.get("/evaluation/reports")
async def list_reports(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """历史评估报告列表"""
    result = await db.execute(
        select(EvaluationReport)
        .where(EvaluationReport.user_id == current_user.id)
        .order_by(EvaluationReport.created_at.desc())
        .limit(20)
    )
    reports = result.scalars().all()
    return {"reports": reports, "total": len(reports)}


@router.get("/evaluation/reports/{report_id}")
async def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """单次评估报告详情"""
    result = await db.execute(
        select(EvaluationReport).where(
            EvaluationReport.id == report_id,
            EvaluationReport.user_id == current_user.id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return report
