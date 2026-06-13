from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.security import get_current_user
from core.database import get_db
from models.user import User
from models.study import StudyPlan, StudyRecord
from schemas.study import StudyPlanCreate, StudyPlanResponse, StudyRecordCreate, StudyRecordResponse

router = APIRouter()


@router.post("/plans", response_model=StudyPlanResponse)
async def create_plan(
    body: StudyPlanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = StudyPlan(user_id=current_user.id, **body.model_dump())
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


@router.get("/plans", response_model=list[StudyPlanResponse])
async def list_plans(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StudyPlan)
        .where(StudyPlan.user_id == current_user.id)
        .order_by(StudyPlan.created_at.desc())
    )
    return result.scalars().all()


@router.post("/generate-plans", response_model=list[StudyPlanResponse])
async def generate_plans(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """调用 Planner Agent 根据用户诊断信息生成学习计划"""
    from agents.planner_agent import run_plan

    diagnosis = {
        "target_school": current_user.target_school or "",
        "target_major": current_user.target_major or "",
        "current_level": current_user.current_level,
        "available_hours": current_user.available_hours,
        "learning_style": current_user.learning_style or "",
    }

    result = await run_plan(
        {"user_id": current_user.id, "diagnosis": diagnosis}
    )

    # 删除旧计划，写入新计划
    old = await db.execute(
        select(StudyPlan).where(StudyPlan.user_id == current_user.id)
    )
    for plan in old.scalars().all():
        await db.delete(plan)

    plans = []
    for phase in result.get("phases", []):
        plan = StudyPlan(
            user_id=current_user.id,
            phase=phase.get("phase", "未知阶段"),
            focus=phase.get("focus"),
            start_date=phase.get("start_date"),
            end_date=phase.get("end_date"),
            daily_tasks=phase.get("daily_tasks"),
            status=phase.get("status", "active"),
        )
        db.add(plan)
        plans.append(plan)

    await db.commit()
    for p in plans:
        await db.refresh(p)
    return plans


@router.post("/records", response_model=StudyRecordResponse)
async def create_record(
    body: StudyRecordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = StudyRecord(user_id=current_user.id, **body.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.get("/records", response_model=list[StudyRecordResponse])
async def list_records(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StudyRecord)
        .where(StudyRecord.user_id == current_user.id)
        .order_by(StudyRecord.created_at.desc())
        .limit(100)
    )
    return result.scalars().all()
