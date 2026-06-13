from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(50))
    hashed_password: Mapped[str] = mapped_column(String(200))
    avatar: Mapped[str | None] = mapped_column(String(500), default=None)

    target_school: Mapped[str | None] = mapped_column(String(100), default=None)
    target_major: Mapped[str | None] = mapped_column(String(100), default=None)
    current_level: Mapped[str | None] = mapped_column(String(50), default=None)
    available_hours: Mapped[int | None] = mapped_column(default=None)
    learning_style: Mapped[str | None] = mapped_column(String(30), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
