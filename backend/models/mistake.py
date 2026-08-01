from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class MistakeCategory(Base):
    __tablename__ = "mistake_categories"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserMistake(Base):
    __tablename__ = "user_mistakes"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    mistake_name: Mapped[str] = mapped_column(
        String(64), ForeignKey("mistake_categories.name", ondelete="CASCADE"), primary_key=True
    )
    times: Mapped[int] = mapped_column(Integer, default=0)
    first_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MistakeOccursIn(Base):
    __tablename__ = "mistake_occurs_in"

    mistake_name: Mapped[str] = mapped_column(
        String(64), ForeignKey("mistake_categories.name", ondelete="CASCADE"), primary_key=True
    )
    kp_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), primary_key=True
    )
    count: Mapped[int] = mapped_column(Integer, default=0)
    last_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
