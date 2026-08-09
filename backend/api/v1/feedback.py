"""阶段五·2C Feedback API：用户对 GraphRAG 回答的 👍/👎。

POST /feedback/kg-answer
  body: {
    query: str,
    answer: str,
    cited_concepts: list[{id, name, type}],
    rating: -1 | 0 | 1,           -1=👎, 0=中性, 1=👍
    client_ip?: str,
    user_agent?: str,
  }

约束：
- rating=1（赞）必须含至少 1 个 cited_concepts（防止灌水 + 保证答案有事实依据）
- query_hash 用 md5 前 16 位做去重键
- client_ip / user_agent 透传自前端 header，落库做飞轮分析用
"""
from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from models.user import User


router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackReq(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    answer: str = Field(..., min_length=1, max_length=5000)
    cited_concepts: list[dict] = Field(default_factory=list)
    rating: int = Field(..., ge=-1, le=1)
    client_ip: str | None = None
    user_agent: str | None = None


@router.post("/kg-answer")
async def submit_kg_feedback(
    body: FeedbackReq,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cited_ids = [
        c.get("id") for c in body.cited_concepts
        if isinstance(c, dict) and c.get("id")
    ]
    if not cited_ids and body.rating == 1:
        raise HTTPException(400, "赞的回答必须含 cited_concepts")

    query_hash = hashlib.md5(body.query.encode("utf-8")).hexdigest()[:16]
    client_ip = body.client_ip or (request.client.host if request.client else None)
    ua = body.user_agent or request.headers.get("user-agent", "") or ""

    await db.execute(
        text("""
            INSERT INTO feedback_kg_answer
                (user_id, query, query_hash, answer, cited_concepts,
                 rating, client_ip, user_agent, created_at)
            VALUES
                (:uid, :q, :qh, :a, CAST(:cited AS JSONB),
                 :r, :ip, :ua, now())
        """),
        {
            "uid": user.id,
            "q": body.query,
            "qh": query_hash,
            "a": body.answer,
            "cited": json.dumps(cited_ids, ensure_ascii=False),
            "r": body.rating,
            "ip": (client_ip or "")[:45],
            "ua": ua[:500],
        },
    )
    await db.commit()
    return {"ok": True}