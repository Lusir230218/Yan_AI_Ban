"""阶段五·2C KG 检索 API（8 个端点）。

按 P1-1 修正：使用 `core.database.async_session` + SQLAlchemy text()，
不复用不存在的 `from db import get_pg_session`。

按 P1-2 修正：`embed_text` 在 kg.embedding_pipeline 中已公开（原 _embed_text）。
按 P2-1 修正：所有 Neo4j 调用都是 `await (await s.run(...)).data()`。

端点清单：
  POST   /kg/search                GraphRAG 检索 + 生成
  GET    /kg/concept/{id}          概念详情 + 1 跳邻居
  GET    /kg/study-recommendations 基于 PG user_kp_mastery 的学习推荐
  GET    /kg/path?from=&to=        两概念最短路径
  GET    /kg/similar-concepts/{id} 向量相似概念
  GET    /kg/admin/review-queue    admin 待 review 候选（2B candidates 表）
  POST   /kg/admin/approve         admin 批准候选
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from config import settings
from core.database import async_session
from core.security import get_current_user, require_admin
from kg.graph_rag import GraphRAG
from kg.neo4j_client import kg_session
from models.user import User


router = APIRouter(prefix="/kg", tags=["knowledge_graph"])


# ===== GraphRAG 单例 =====

_graph_rag: GraphRAG | None = None


def get_graph_rag() -> GraphRAG:
    """懒加载单例 — 避免每次请求重建。

    故意在函数体内 import chat_json / embed_text，让测试用 mock.patch
    `kg.llm_client.chat_json` 时也能生效（patch 模块属性 vs local binding 的坑）。
    """
    global _graph_rag
    if _graph_rag is None:
        from kg.embedding_pipeline import embed_text as _embed_text
        from kg.llm_client import chat_json as _chat_json

        _graph_rag = GraphRAG(
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_dim=settings.EMBEDDING_DIM,
            llm_call=_chat_json,
            embed_call=_embed_text,
        )
    return _graph_rag


def reset_graph_rag() -> None:
    """测试 hook：清掉单例。"""
    global _graph_rag
    _graph_rag = None


# ===== Pydantic schemas =====


class GraphSearchReq(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)


# ===== 1. POST /kg/search =====


@router.post("/search")
async def kg_search(
    body: GraphSearchReq,
    user: User = Depends(get_current_user),
):
    rag = get_graph_rag()
    result = await rag.generate_with_context(body.query, user.id)
    return {
        "answer": result.answer,
        "cited": result.cited,
        "seeds": [_node_to_dict(n) for n in result.seeds],
        "expanded": [_node_to_dict(n) for n in result.expanded],
        "fallback": result.fallback,
        "used_token_estimate": result.used_token_estimate,
    }


def _node_to_dict(n) -> dict:
    """把 RetrievedNode 序列化成 dict（用于 API 响应）。"""
    return {
        "id": n.id,
        "name": n.name,
        "type": n.type,
        "subject": n.subject,
        "pg_kp_id": n.pg_kp_id,
        "vector_score": round(n.vector_score, 3),
        "confidence": round(n.confidence, 3),
        "mastery": n.mastery,
    }


# ===== 2. GET /kg/concept/{concept_id} =====


@router.get("/concept/{concept_id}")
async def concept_detail(
    concept_id: str,
    user: User = Depends(get_current_user),
):
    async with kg_session() as s:
        node = await (await s.run(
            "MATCH (c:Concept {id: $id}) RETURN c {.*} AS c",
            id=concept_id,
        )).single()
        if not node:
            raise HTTPException(404, "concept not found")

        prereqs = await (await s.run("""
            MATCH (c:Concept {id: $id})-[:PREREQUISITE_OF]->(pre:Concept)
            RETURN pre.id AS id, pre.name AS name, pre.type AS type
            ORDER BY pre.confidence DESC
            LIMIT 20
        """, id=concept_id)).data()

        nexts = await (await s.run("""
            MATCH (next:Concept)-[:PREREQUISITE_OF]->(c:Concept {id: $id})
            RETURN next.id AS id, next.name AS name, next.type AS type
            ORDER BY next.confidence DESC
            LIMIT 20
        """, id=concept_id)).data()

        mistakes = await (await s.run("""
            MATCH (m:Mistake)-[:COMMON_MISTAKE_OF]->(c:Concept {id: $id})
            RETURN m.id AS id, m.name AS name
            LIMIT 10
        """, id=concept_id)).data()

    user_state: dict | None = None
    concept_raw = node["c"]
    concept = dict(concept_raw) if isinstance(concept_raw, dict) else dict(concept_raw.items())
    pg_kp_id = concept.get("pg_kp_id")
    if pg_kp_id:
        rag = get_graph_rag()
        m = await rag._fetch_user_state(user.id, [int(pg_kp_id)])
        user_state = m.get(int(pg_kp_id))

    return {
        "concept": concept,
        "prerequisites": prereqs,
        "next_concepts": nexts,
        "common_mistakes": mistakes,
        "user_state": user_state,
    }


# ===== 3. GET /kg/study-recommendations =====


@router.get("/study-recommendations")
async def study_recommendations(
    limit: int = Query(5, ge=1, le=20),
    user: User = Depends(get_current_user),
):
    weak_ids = await _user_weak_pg_kp_ids(user.id, limit=10)
    if not weak_ids:
        return []
    mastered_ids = await _user_mastered_pg_kp_ids(user.id)
    async with kg_session() as s:
        rows = await (await s.run("""
            MATCH (weak:Concept)
            WHERE weak.pg_kp_id IN $weak_ids
            MATCH (root)-[:PREREQUISITE_OF*1..3]->(weak)
            WHERE NOT EXISTS {
                MATCH (deeper)-[:PREREQUISITE_OF]->(root)
                WHERE deeper.pg_kp_id IN $mastered_ids
            }
            WITH weak, root,
                 length((root)-[:PREREQUISITE_OF*]->(weak)) AS depth
            RETURN DISTINCT
                root.id AS root_id, root.name AS root_name,
                root.type AS root_type,
                weak.id AS weak_id, weak.name AS weak_name,
                weak.pg_kp_id AS weak_pg_id, depth
            ORDER BY depth ASC, root.confidence DESC
            LIMIT $limit
        """, weak_ids=weak_ids,
             mastered_ids=mastered_ids,
             limit=limit)).data()
    return rows


# ===== 4. GET /kg/path =====


@router.get("/path")
async def path_between(
    from_id: str = Query(..., alias="from"),
    to_id: str = Query(..., alias="to"),
    user: User = Depends(get_current_user),
):
    async with kg_session() as s:
        row = await (await s.run("""
            MATCH p = shortestPath(
                (a:Concept {id: $from})-[*..6]-(b:Concept {id: $to})
            )
            RETURN [n IN nodes(p) | n.id] AS path
        """, **{"from": from_id, "to": to_id})).single()
    if not row:
        raise HTTPException(404, "no path")
    return {"path": row["path"]}


# ===== 5. GET /kg/similar-concepts/{concept_id} =====


@router.get("/similar-concepts/{concept_id}")
async def similar_concepts(
    concept_id: str,
    limit: int = Query(5, ge=1, le=20),
    user: User = Depends(get_current_user),
):
    async with kg_session() as s:
        rows = await (await s.run("""
            MATCH (seed:Concept {id: $id})
            CALL db.index.vector.queryNodes(
                'concept_embedding', $k_plus, seed.embedding
            )
            YIELD node AS n, score
            WHERE n.id <> $id AND n.status = 'active'
            RETURN n.id AS id, n.name AS name, n.type AS type,
                   n.subject AS subject, score
            LIMIT $k
        """, id=concept_id, k=limit, k_plus=limit + 1)).data()
    return rows


# ===== 6. GET /kg/admin/review-queue =====


@router.get("/admin/review-queue")
async def admin_review_queue(
    user: User = Depends(get_current_user),
    _: User = Depends(require_admin),
):
    """2B candidates 表的 pending 列表。kg_review_queue 表不复建（P2-2）。"""
    async with async_session() as db:
        result = await db.execute(text("""
            SELECT id, kind, payload, status, created_at
            FROM kg_extraction_candidates
            WHERE status = 'pending'
            ORDER BY created_at DESC
            LIMIT 50
        """))
        rows = result.all()
    return [dict(r._mapping) for r in rows]


# ===== 7. POST /kg/admin/approve =====


@router.post("/admin/approve")
async def admin_approve(
    body: dict[str, Any],
    user: User = Depends(get_current_user),
    _: User = Depends(require_admin),
):
    """body: {candidate_id: int, kind: str}"""
    kind = body.get("kind")
    cand_id = body.get("candidate_id")
    if cand_id is None or kind is None:
        raise HTTPException(400, "kind and candidate_id are required")

    if kind == "low_conf_relation":
        async with async_session() as db:
            result = await db.execute(
                text("""
                    UPDATE kg_extraction_candidates
                    SET status = 'approved', reviewed_at = now()
                    WHERE id = :id
                    RETURNING payload
                """),
                {"id": int(cand_id)},
            )
            row = result.first()
            await db.commit()
        if row:
            payload = row[0]
            from kg.extract import _persist_extraction
            await _persist_extraction(
                payload,
                source="admin:approved",
                source_ref=f"cand:{cand_id}",
                subject=(payload.get("subject") if isinstance(payload, dict) else None) or "unknown",
            )
    elif kind == "concept_conflict":
        from kg.merge_dups import merge_duplicates
        await merge_duplicates()
    else:
        # 其他 kind（chunk_seen / unresolved_chunk）只更新状态
        async with async_session() as db:
            await db.execute(
                text("""
                    UPDATE kg_extraction_candidates
                    SET status = 'approved', reviewed_at = now()
                    WHERE id = :id
                """),
                {"id": int(cand_id)},
            )
            await db.commit()
    return {"ok": True, "candidate_id": cand_id}


# ===== Helpers =====


async def _user_weak_pg_kp_ids(user_id: int, limit: int) -> list[int]:
    async with async_session() as db:
        result = await db.execute(
            text("""
                SELECT kp_id FROM user_kp_mastery
                WHERE user_id = :u AND score < 0.5
                ORDER BY score ASC LIMIT :lim
            """),
            {"u": user_id, "lim": limit},
        )
        rows = result.all()
    return [int(r.kp_id) for r in rows]


async def _user_mastered_pg_kp_ids(user_id: int) -> list[int]:
    async with async_session() as db:
        result = await db.execute(
            text("""
                SELECT kp_id FROM user_kp_mastery
                WHERE user_id = :u AND score >= 0.8
            """),
            {"u": user_id},
        )
        rows = result.all()
    return [int(r.kp_id) for r in rows]