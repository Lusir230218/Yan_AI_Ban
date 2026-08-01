from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from core.database import get_db
from core.security import get_current_user
from models.mistake import MistakeCategory, MistakeOccursIn, UserMistake
from models.study import (
    KnowledgePoint,
    Question,
    QuestionGroup,
    StudyRecord,
    UserKpMastery,
    UserKpWeak,
)
from models.user import User
from schemas.study import (
    AnswerResult,
    AnswerSubmit,
    KnowledgePointResponse,
    KnowledgePointTree,
    QuestionCreate,
    QuestionResponse,
    StudyRecordResponse,
)
from services.mastery_calc import compute_score

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
    kp_id = question.knowledge_point_id
    user_id = current_user.id
    source = body.source or "human"
    error_category = (body.error_category or "").strip()[:64] or None

    # 1. 写 study_records（真值源）
    record = StudyRecord(
        user_id=user_id,
        subject=body.subject,
        knowledge_point_id=kp_id,
        question_id=question.id,
        is_correct=is_correct,
        duration_seconds=body.duration_seconds,
        error_category=error_category,
        source=source,
    )
    db.add(record)
    await db.flush()

    if kp_id is not None:
        # 2. UPSERT user_kp_mastery
        await db.execute(
            pg_insert(UserKpMastery).values(
                user_id=user_id,
                kp_id=kp_id,
                correct_count=1 if is_correct else 0,
                total_count=1,
                last_reviewed=record.created_at,
                review_count=1,
                source_primary=source,
            ).on_conflict_do_update(
                index_elements=["user_id", "kp_id"],
                set_={
                    "correct_count": UserKpMastery.correct_count + (1 if is_correct else 0),
                    "total_count": UserKpMastery.total_count + 1,
                    "last_reviewed": record.created_at,
                    "review_count": UserKpMastery.review_count + 1,
                    # human 一旦置位就保留
                    "source_primary": case(
                        (UserKpMastery.source_primary == "human", "human"),
                        else_=source,
                    ),
                },
            )
        )

        # 3. 答错时 UPSERT user_kp_weak
        if not is_correct:
            await db.execute(
                pg_insert(UserKpWeak).values(
                    user_id=user_id,
                    kp_id=kp_id,
                    error_count=1,
                    last_error_at=record.created_at,
                ).on_conflict_do_update(
                    index_elements=["user_id", "kp_id"],
                    set_={
                        "error_count": UserKpWeak.error_count + 1,
                        "last_error_at": record.created_at,
                    },
                )
            )

        # 4. 错因 upsert（仅当答错且 error_category 非空）
        if not is_correct and error_category:
            # 4a) 错因字典
            await db.execute(
                pg_insert(MistakeCategory)
                .values(name=error_category)
                .on_conflict_do_nothing()
            )
            # 4b) 用户错因累计
            await db.execute(
                pg_insert(UserMistake).values(
                    user_id=user_id,
                    mistake_name=error_category,
                    times=1,
                    first_at=record.created_at,
                    last_at=record.created_at,
                ).on_conflict_do_update(
                    index_elements=["user_id", "mistake_name"],
                    set_={
                        "times": UserMistake.times + 1,
                        "last_at": record.created_at,
                    },
                )
            )
            # 4c) 错因→KP 关联
            await db.execute(
                pg_insert(MistakeOccursIn).values(
                    mistake_name=error_category,
                    kp_id=kp_id,
                    count=1,
                    last_at=record.created_at,
                ).on_conflict_do_update(
                    index_elements=["mistake_name", "kp_id"],
                    set_={
                        "count": MistakeOccursIn.count + 1,
                        "last_at": record.created_at,
                    },
                )
            )

        # 5. score 重算
        if settings.MASTERY_RECOMPUTE_ON_ANSWER:
            score = await compute_score(db, user_id, kp_id)
            await db.execute(
                UserKpMastery.__table__.update()
                .where(UserKpMastery.user_id == user_id, UserKpMastery.kp_id == kp_id)
                .values(score=score)
            )

    await db.commit()
    await db.refresh(record)

    return AnswerResult(
        is_correct=is_correct,
        correct_answer=question.correct_answer,
        explanation=question.explanation,
        record=StudyRecordResponse.model_validate(record),
    )
