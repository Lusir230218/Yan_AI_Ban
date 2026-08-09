"""阶段五·2C PG 模型：feedback_kg_answer + gap_questions。

- FeedbackKGAnswer: 用户对 GraphRAG 回答的 👍/👎。2D 飞轮读这张表。
- GapQuestion: 图谱覆盖不了的问题。用于缺口检测。

注：原 doc 中的 kg_review_queue 表，2B 已建 kg_extraction_candidates（kind=low_conf_relation）
覆盖同语义字段，本期不建新表。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Float, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class FeedbackKGAnswer(Base):
    """用户对 GraphRAG 回答的 👍/👎。2D 飞轮读这张表。"""
    __tablename__ = "feedback_kg_answer"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    query: Mapped[str] = mapped_column(Text)
    query_hash: Mapped[str] = mapped_column(String(16), index=True)
    answer: Mapped[str] = mapped_column(Text)
    cited_concepts: Mapped[list] = mapped_column(JSON)
    rating: Mapped[int] = mapped_column(SmallInteger)  # -1 / 0 / 1
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True,
    )


class GapQuestion(Base):
    """图谱覆盖不了的问题。用于缺口检测。"""
    __tablename__ = "gap_questions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    query: Mapped[str] = mapped_column(Text)
    top_score: Mapped[float] = mapped_column(Float, default=0.0)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True,
    )