"""阶段五·2D 飞轮：4 类信号采集。

信号统一表示: (kind, concept_id, signal_value, occurred_at)
- kind:        "feedback" | "implicit" | "cross_source" | "gap"
- concept_id:  Neo4j Concept.id (string, e.g. "kp:MA-INT-001")
- signal_value: 1.0 赞 / 0.0 踩 / 0.5 中性
- occurred_at:  信号发生时间

下家: kg.flywheel 聚合并调 batch_update() 算 EMA。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from core.database import async_session
from kg.neo4j_client import kg_session


# ───────────────────────── 用户量 ─────────────────────────


async def fetch_total_user_count() -> int:
    """累计用户数（用于决定 EMA 学习率）。"""
    async with async_session() as db:
        row = (await db.execute(text("""
            SELECT count(*) AS n FROM users
        """))).first()
    return int(row[0]) if row else 0


# ─────────────────── ① 显式反馈（👍/👎）──────────────────


async def signals_explicit_feedback(since: datetime) -> list[tuple]:
    """用户对 GraphRAG 回答的 👍/👎，每条 cited_concept 摊开为一条信号。

    Returns:
        [(kind, concept_id, signal_value, occurred_at), ...]
    """
    async with async_session() as db:
        rows = (await db.execute(text("""
            SELECT cited_concepts, rating, created_at
            FROM feedback_kg_answer
            WHERE created_at > :since AND rating != 0
        """), {"since": since})).all()

    out: list[tuple] = []
    for r in rows:
        signal = 1.0 if r.rating == 1 else 0.0
        for cid in (r.cited_concepts or []):
            # cited_concepts 在 PG 里是 JSONB 数组，可能是 [str, ...] 或 [{id: str}, ...]
            if isinstance(cid, dict):
                cid = cid.get("id")
            if not cid:
                continue
            out.append(("feedback", cid, signal, r.created_at))
    return out


# ─────────────────── ② 隐式反馈（答对/答错）──────────────────


async def signals_implicit_feedback(since: datetime) -> list[tuple]:
    """用户问完 AI 后 5 分钟内答了相关题 — 把每道题答题结果当作信号的代理。

    拼接逻辑：feedback_kg_answer.created_at 后 5 分钟内的 study_records。
    """
    async with async_session() as db:
        rows = (await db.execute(text("""
            WITH recent_fb AS (
                SELECT id, user_id, cited_concepts, created_at
                FROM feedback_kg_answer
                WHERE created_at > :since
            )
            SELECT rf.cited_concepts, rq.is_correct, rq.created_at
            FROM recent_fb rf
            JOIN study_records rq
              ON rf.user_id = rq.user_id
             AND rq.created_at BETWEEN rf.created_at
                 AND rf.created_at + INTERVAL '5 minutes'
        """), {"since": since})).all()

    out: list[tuple] = []
    for r in rows:
        signal = 1.0 if r.is_correct else 0.0
        for cid in (r.cited_concepts or []):
            if isinstance(cid, dict):
                cid = cid.get("id")
            if not cid:
                continue
            out.append(("implicit", cid, signal, r.created_at))
    return out


# ─────────────────── ③ 跨源验证（Neo4j 内置）──────────────────


async def signals_cross_source(since: datetime) -> list[tuple]:
    """Neo4j 关系 updated_at > since 且未被 disputed → 把 confidence 当作弱信号。

    注：返回 (kind, concept_id, signal, occurred_at)，concept_id 用 Neo4j rel_id。
    调用方不直接消费这条信号（flywheel 主要吃 ① + ②），
    这里保留接口为后续跨源比对留位。
    """
    async with kg_session() as s:
        rows = await (await s.run("""
            MATCH ()-[r]->()
            WHERE r.updated_at > $since AND coalesce(r.disputed, false) = false
            RETURN elementId(r) AS rel_id, r.confidence AS conf, r.updated_at AS updated
        """, since=since)).data()
    return [
        ("cross_source", str(r["rel_id"]), float(r["conf"]), r["updated"])
        for r in rows
    ]


# ─────────────────── ④ 缺口检测（覆盖不到的问题）──────────────────


async def fetch_gap_questions(limit: int = 100) -> list[dict]:
    """最近 7 天的高频未覆盖查询，附到 admin 报表作为后续抽取的候选。"""
    async with async_session() as db:
        rows = (await db.execute(text("""
            SELECT query, count(*) AS n FROM gap_questions
            WHERE created_at > now() - INTERVAL '7 days'
            GROUP BY query ORDER BY n DESC LIMIT :lim
        """), {"lim": limit})).all()
    return [{"query": r[0], "count": int(r[1])} for r in rows]