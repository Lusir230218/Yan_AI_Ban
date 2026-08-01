from datetime import datetime, date

from sqlalchemy import String, Integer, Float, Boolean, Date, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    phase: Mapped[str] = mapped_column(String(20))
    focus: Mapped[str | None] = mapped_column(String(100), default=None)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    daily_tasks: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(50))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_points.id"), default=None)
    level: Mapped[int] = mapped_column(Integer, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    applicable_variants: Mapped[str | None] = mapped_column(String(100), default=None)
    exam_frequency: Mapped[int] = mapped_column(Integer, default=1)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    prerequisites: Mapped[str | None] = mapped_column(Text, default=None)
    chapter: Mapped[str | None] = mapped_column(String(100), default=None)
    section: Mapped[str | None] = mapped_column(String(100), default=None)


class StudyRecord(Base):
    __tablename__ = "study_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject: Mapped[str] = mapped_column(String(50))
    knowledge_point_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_points.id"), default=None)
    question_id: Mapped[int | None] = mapped_column(default=None)
    is_correct: Mapped[bool | None] = mapped_column(default=None)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    emotion_score: Mapped[float | None] = mapped_column(Float, default=None)
    error_category: Mapped[str | None] = mapped_column(String(64), default=None)
    source: Mapped[str] = mapped_column(String(10), default="human")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserKpMastery(Base):
    __tablename__ = "user_kp_mastery"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    kp_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id", ondelete="CASCADE"), primary_key=True)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.5)
    last_reviewed: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)
    source_primary: Mapped[str] = mapped_column(String(10), default="human")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UserKpWeak(Base):
    __tablename__ = "user_kp_weak"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    kp_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id", ondelete="CASCADE"), primary_key=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MasterySnapshot(Base):
    __tablename__ = "mastery_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kp_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"), index=True)
    subject: Mapped[str] = mapped_column(String(50))
    score: Mapped[float] = mapped_column(Float)
    delta: Mapped[float | None] = mapped_column(Float, default=None)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class QuestionGroup(Base):
    __tablename__ = "question_groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(50))
    title: Mapped[str | None] = mapped_column(String(200), default=None)
    content: Mapped[str] = mapped_column(Text, default="")
    images: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    questions = relationship("Question", back_populates="group", order_by="Question.group_order")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    question_type: Mapped[str] = mapped_column(String(30))
    subject: Mapped[str] = mapped_column(String(50))
    exam_variant: Mapped[str | None] = mapped_column(String(20), default=None)
    knowledge_point_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_points.id"), default=None)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("question_groups.id"), default=None)
    group_order: Mapped[int | None] = mapped_column(Integer, default=None)
    stem: Mapped[str] = mapped_column(Text)
    options: Mapped[str] = mapped_column(Text)
    correct_answer: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text, default=None)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    images: Mapped[str | None] = mapped_column(Text, default=None)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    group = relationship("QuestionGroup", back_populates="questions")
    knowledge_point = relationship("KnowledgePoint")
