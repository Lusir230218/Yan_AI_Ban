from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.security import get_current_user
from core.database import get_db
from models.user import User
from models.study import Question, StudyRecord
from schemas.study import (
    QuestionCreate,
    QuestionResponse,
    AnswerSubmit,
    AnswerResult,
    StudyRecordResponse,
)

router = APIRouter()


@router.get("", response_model=list[QuestionResponse])
async def list_questions(
    subject: str | None = Query(None),
    knowledge_point_id: int | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Question).order_by(Question.created_at.desc())
    if subject:
        stmt = stmt.where(Question.subject == subject)
    if knowledge_point_id:
        stmt = stmt.where(Question.knowledge_point_id == knowledge_point_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{question_id}", response_model=QuestionResponse)
async def get_question(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Question).where(Question.id == question_id))
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

    is_correct = body.answer.strip().upper() == question.correct_answer.strip().upper()

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
