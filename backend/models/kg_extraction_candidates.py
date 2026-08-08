"""阶段五·2B 候选表 PG 模型。

三种 kind:
- 'concept_conflict'   同名不同 type，待人工 review
- 'low_conf_relation'  conf < 0.5 的关系，不进 Neo4j
- 'unresolved_chunk'   3 轮重试都失败的 chunk
- 'chunk_seen'         已处理的 chunk_id（用于 --incremental 增量跑）
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, JSON, SmallInteger, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from core.database import Base


class KGExtractionCandidate(Base):
    __tablename__ = "kg_extraction_candidates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/done/approved/rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)