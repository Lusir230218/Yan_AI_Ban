from datetime import datetime, date

from sqlalchemy import String, Integer, Float, Boolean, Date, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

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
    name: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(50))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_points.id"), default=None)
    exam_frequency: Mapped[int] = mapped_column(Integer, default=1)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    prerequisites: Mapped[str | None] = mapped_column(Text, default=None)


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    question_type: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(50))
    knowledge_point_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_points.id"), default=None)
    stem: Mapped[str] = mapped_column(Text)
    options: Mapped[str] = mapped_column(Text)
    correct_answer: Mapped[str] = mapped_column(String(10))
    explanation: Mapped[str | None] = mapped_column(Text, default=None)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
