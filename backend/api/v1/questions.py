from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.security import get_current_user
from core.database import get_db
from models.user import User
from models.study import Question, StudyRecord, KnowledgePoint, QuestionGroup
from schemas.study import (
    QuestionCreate,
    QuestionResponse,
    KnowledgePointResponse,
    KnowledgePointTree,
    AnswerSubmit,
    AnswerResult,
    StudyRecordResponse,
)

router = APIRouter()


# ── Knowledge Points ──

@router.get("/knowledge-points", response_model=list[KnowledgePointResponse])
async def list_knowledge_points(
    subject: str | None = Query(None),
    exam_variant: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(KnowledgePoint).order_by(KnowledgePoint.sort_order)
    if subject:
        stmt = stmt.where(KnowledgePoint.subject == subject)
    if exam_variant:
        stmt = stmt.where(
            (KnowledgePoint.applicable_variants.contains(exam_variant))
            | (KnowledgePoint.applicable_variants.is_(None))
        )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/knowledge-points/tree", response_model=list[KnowledgePointTree])
async def get_knowledge_tree(
    subject: str | None = Query(None),
    exam_variant: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(KnowledgePoint).order_by(KnowledgePoint.sort_order)
    if subject:
        stmt = stmt.where(KnowledgePoint.subject == subject)
    if exam_variant:
        stmt = stmt.where(
            (KnowledgePoint.applicable_variants.contains(exam_variant))
            | (KnowledgePoint.applicable_variants.is_(None))
        )
    result = await db.execute(stmt)
    nodes = result.scalars().all()

    by_id: dict[int, KnowledgePointTree] = {}
    roots: list[KnowledgePointTree] = []

    for n in nodes:
        node = KnowledgePointTree(id=n.id, code=n.code, name=n.name, level=n.level, children=[])
        by_id[n.id] = node
        if n.parent_id and n.parent_id in by_id:
            by_id[n.parent_id].children.append(node)
        else:
            roots.append(node)

    return roots


# ── Questions ──

@router.get("", response_model=list[QuestionResponse])
async def list_questions(
    subject: str | None = Query(None),
    exam_variant: str | None = Query(None),
    question_type: str | None = Query(None),
    knowledge_point_id: int | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Question).options(
        selectinload(Question.group),
        selectinload(Question.knowledge_point),
    ).order_by(Question.created_at.desc())
    if subject:
        stmt = stmt.where(Question.subject == subject)
    if exam_variant:
        stmt = stmt.where(Question.exam_variant == exam_variant)
    if question_type:
        stmt = stmt.where(Question.question_type == question_type)
    if knowledge_point_id:
        stmt = stmt.where(Question.knowledge_point_id == knowledge_point_id)
    result = await db.execute(stmt)
    return result.scalars().unique().all()


@router.get("/{question_id}", response_model=QuestionResponse)
async def get_question(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Question).options(
        selectinload(Question.group),
        selectinload(Question.knowledge_point),
    ).where(Question.id == question_id)
    result = await db.execute(stmt)
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    return question


@router.post("", response_model=QuestionResponse)
async def create_question(
    body: QuestionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    question = Question(**body.model_dump())
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return question


@router.delete("/{question_id}")
async def delete_question(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    await db.delete(question)
    await db.commit()
    return {"ok": True}


@router.post("/{question_id}/submit", response_model=AnswerResult)
async def submit_answer(
    question_id: int,
    body: AnswerSubmit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    user_ans = body.answer.strip().upper().replace(" ", "")
    correct_ans = question.correct_answer.strip().upper().replace(" ", "")
    is_correct = user_ans == correct_ans

    record = StudyRecord(
        user_id=current_user.id,
        subject=body.subject,
        knowledge_point_id=question.knowledge_point_id,
        question_id=question.id,
        is_correct=is_correct,
        duration_seconds=body.duration_seconds,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return AnswerResult(
        is_correct=is_correct,
        correct_answer=question.correct_answer,
        explanation=question.explanation,
        record=StudyRecordResponse.model_validate(record),
    )
