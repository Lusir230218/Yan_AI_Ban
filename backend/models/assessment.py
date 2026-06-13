from datetime import datetime

from sqlalchemy import String, Float, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class ExamGrading(Base):
    __tablename__ = "exam_gradings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject: Mapped[str] = mapped_column(String(50))
    exam_image_url: Mapped[str | None] = mapped_column(String(500), default=None)
    ocr_text: Mapped[str | None] = mapped_column(Text, default=None)
    grading_result: Mapped[str | None] = mapped_column(Text, default=None)
    error_analysis: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvaluationReport(Base):
    __tablename__ = "evaluation_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    period: Mapped[str] = mapped_column(String(20))
    predicted_score: Mapped[float | None] = mapped_column(Float, default=None)
    weak_points: Mapped[str | None] = mapped_column(Text, default=None)
    suggestions: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
