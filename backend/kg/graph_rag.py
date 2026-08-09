"""阶段五·2C GraphRAG 主流程 — 对单 query 的检索 + 生成。

流程：
1. embed query → 向量召回 top_k seeds（按 embedding_model 过滤跨模型）
2. 1 跳图扩展（PREREQUISITE_OF 下游 + COMMON_MISTAKE_OF 上游 + CONTRASTS_WITH 双向）
   过滤 confidence < 0.4 的节点（防止飞轮误注入扩散）
3. PG user_kp_mastery JOIN → 注入 mastery 状态
4. 按 priority 排序 + token 截断到 max_tokens
5. 拼 RAG prompt → LLM 出 JSON（{answer, cited}）
6. fallback：图谱未覆盖 → 返回 syllabus KP + 写 gap_questions

⚠️ P2-1 注意：Neo4j async 的 AsyncResult.data() 也是 coroutine，
   必须 `await (await s.run(...)).data()`，单 await 会漏掉。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from sqlalchemy import text

from core.database import async_session
from kg.embedding_pipeline import embed_text
from kg.llm_client import LLMError
from kg.neo4j_client import kg_session
from kg.prompts_rag import build_rag_prompt
from kg.token_budget import PrioritizedContext, prioritize_and_truncate

logger = logging.getLogger(__name__)


# ===================== 数据结构 =====================


@dataclass
class RetrievedNode:
    """从 Neo4j 召回 / 扩展出来的概念节点。"""
    id: str
    name: str
    type: str
    subject: str = "unknown"
    pg_kp_id: int | None = None
    vector_score: float = 0.0       # 0..1
    confidence: float = 0.0          # 0..1
    mastery: dict | None = None      # 来自 PG user_kp_mastery


@dataclass
class GraphRAGResult:
    """端到端 RAG 结果（API 层直接序列化）。"""
    answer: str
    cited: list[dict[str, str]] = field(default_factory=list)  # [{id, name, type}]
    seeds: list[RetrievedNode] = field(default_factory=list)
    expanded: list[RetrievedNode] = field(default_factory=list)
    used_token_estimate: int = 0
    fallback: bool = False


# ===================== LLM/Embed callable type =====================


EmbedCall = Callable[[str], Awaitable[list[float]]]
LLMCall = Callable[[str], Awaitable[dict[str, Any]]]


# ===================== GraphRAG 主类 =====================


class GraphRAG:
    """对单 query 的 GraphRAG 封装。

    @    rag = GraphRAG(
    @        embedding_model=settings.EMBEDDING_MODEL,
    @        embedding_dim=settings.EMBEDDING_DIM,
    @        llm_call=chat_json,
    @        embed_call=embed_text,
    @    )
    @    result = await rag.generate_with_context("如何学换元法？", user_id=42)
    """

    def __init__(
        self,
        embedding_model: str,
        embedding_dim: int,
        llm_call: LLMCall,
        embed_call: EmbedCall,
        max_context_tokens: int = 3000,
        top_k_seeds: int = 5,
        hop1_limit: int = 12,
        expand_min_confidence: float = 0.4,
    ):
        self.embedding_model = embedding_model
        self.embedding_dim = embedding_dim
        self.llm_call = llm_call
        self.embed_call = embed_call
        self.max_context_tokens = max_context_tokens
        self.top_k_seeds = top_k_seeds
        self.hop1_limit = hop1_limit
        self.expand_min_confidence = expand_min_confidence

    # ----- 顶层入口 -----

    async def generate_with_context(
        self, query: str, user_id: int,
    ) -> GraphRAGResult:
        """端到端：retrieve → 拼上下文 → 调 LLM → 强制结构化输出。"""
        ctx = await self._retrieve(query, user_id)
        if ctx["fallback"]:
            return await self._fallback_answer(query, user_id)

        prioritized = prioritize_and_truncate(
            seeds=ctx["seeds"],
            expanded=ctx["expanded"],
            user_state=ctx["user_state_map"],
            max_tokens=self.max_context_tokens,
        )

        prompt = build_rag_prompt(query, prioritized)

        try:
            llm_out = await self.llm_call(prompt)
        except LLMError as e:
            logger.warning("LLM call failed: %s", e)
            return GraphRAGResult(
                answer="（AI 服务暂时不可用）",
                cited=[],
                seeds=list(prioritized.seeds),
                expanded=list(prioritized.expanded),
                used_token_estimate=prioritized.used_tokens,
                fallback=True,
            )

        return GraphRAGResult(
            answer=str(llm_out.get("answer", "")),
            cited=list(llm_out.get("cited", []) or []),
            seeds=list(prioritized.seeds),
            expanded=list(prioritized.expanded),
            used_token_estimate=prioritized.used_tokens,
            fallback=False,
        )

    # ----- 检索（retrieve） -----

    async def _retrieve(self, query: str, user_id: int) -> dict[str, Any]:
        """向量召回 + 1 跳扩展 + PG 用户状态。fallback 时所有 list 为空。"""
        emb = await self._safe_embed(query)
        if not emb:
            return {
                "seeds": [], "expanded": [],
                "user_state_map": {}, "fallback": True,
            }

        seeds = await self._vector_recall(emb)
        if not seeds:
            return {
                "seeds": [], "expanded": [],
                "user_state_map": {}, "fallback": True,
            }

        expanded = await self._expand_1hop(seeds)
        pg_kp_ids = [n.pg_kp_id for n in (seeds + expanded) if n.pg_kp_id]
        user_state_map = await self._fetch_user_state(user_id, pg_kp_ids)
        for node in (seeds + expanded):
            if node.pg_kp_id and node.pg_kp_id in user_state_map:
                node.mastery = user_state_map[node.pg_kp_id]

        return {
            "seeds": seeds, "expanded": expanded,
            "user_state_map": user_state_map, "fallback": False,
        }

    # ----- 向量召回 -----

    async def _vector_recall(self, emb: list[float]) -> list[RetrievedNode]:
        """按 embedding_model 过滤跨模型；只召回 active 节点。

        向量索引缺失时（例如 prod 未跑 init_kg_schema）返回空 list，
        让上层 _retrieve 走 fallback，而不是 500。
        """
        try:
            async with kg_session() as s:
                rows = await (await s.run("""
                    CALL db.index.vector.queryNodes(
                        'concept_embedding', $k, $emb
                    )
                    YIELD node AS c, score
                    WHERE c.embedding_model = $model
                      AND c.status = 'active'
                    RETURN c.id AS id, c.name AS name, c.type AS type,
                           c.subject AS subject, c.pg_kp_id AS pg_kp_id,
                           c.confidence AS confidence, score
                    ORDER BY score DESC
                    LIMIT $k
                """, k=self.top_k_seeds, emb=emb,
                     model=self.embedding_model)).data()
        except Exception as e:
            # Neo4j 缺向量索引（生产未 apply schema）或网络瞬断 — 走 fallback
            msg = str(e)
            if "no such vector schema index" in msg or "concept_embedding" in msg:
                logger.warning(
                    "Neo4j 缺 concept_embedding 向量索引 — 请跑 "
                    "`python -m kg.schema` 或设置 KG_ENV=dev 让 lifespan 自动 apply。"
                    "本次 query 走 fallback。"
                )
                return []
            raise

        out: list[RetrievedNode] = []
        for r in rows:
            out.append(RetrievedNode(
                id=r["id"],
                name=r["name"],
                type=r["type"],
                subject=r.get("subject", "unknown") or "unknown",
                pg_kp_id=r.get("pg_kp_id"),
                vector_score=float(r["score"]),
                confidence=float(r.get("confidence") or 0.0),
            ))
        return out

    # ----- 1 跳扩展 -----

    async def _expand_1hop(
        self, seeds: list[RetrievedNode],
    ) -> list[RetrievedNode]:
        """PREREQUISITE_OF（下游）+ COMMON_MISTAKE_OF（上游错因）+ CONTRASTS_WITH（双向）。

        过滤 confidence < self.expand_min_confidence 的低置信度节点，
        防止飞轮误注入扩散。
        """
        seed_ids = [s.id for s in seeds]
        if not seed_ids:
            return []

        async with kg_session() as s:
            rows = await (await s.run("""
                MATCH (c:Concept)
                WHERE c.id IN $ids
                OPTIONAL MATCH (c)-[r1:PREREQUISITE_OF]->(pre:Concept)
                OPTIONAL MATCH (m:Mistake)-[r2:COMMON_MISTAKE_OF]->(c)
                OPTIONAL MATCH (c)-[r3:CONTRASTS_WITH]-(contra:Concept)
                WITH c,
                     collect(DISTINCT {
                         id: pre.id, name: pre.name, type: pre.type,
                         subject: pre.subject, pg_kp_id: pre.pg_kp_id,
                         confidence: coalesce(r1.confidence, 0.0)
                     }) AS prereqs,
                     collect(DISTINCT {
                         id: m.id, name: m.name, type: m.type,
                         subject: m.subject, pg_kp_id: m.pg_kp_id,
                         confidence: coalesce(r2.confidence, 0.0)
                     }) AS mistakes,
                     collect(DISTINCT {
                         id: contra.id, name: contra.name, type: contra.type,
                         subject: contra.subject, pg_kp_id: contra.pg_kp_id,
                         confidence: coalesce(r3.confidence, 0.0)
                     }) AS contrasts
                RETURN prereqs, mistakes, contrasts
            """, ids=seed_ids)).data()

        out: list[RetrievedNode] = []
        for r in rows:
            for grp in (r["prereqs"], r["mistakes"], r["contrasts"]):
                for n in grp:
                    if not n or n.get("id") is None:
                        continue
                    out.append(RetrievedNode(
                        id=n["id"],
                        name=n.get("name", ""),
                        type=n.get("type", "Concept"),
                        subject=n.get("subject") or "unknown",
                        pg_kp_id=n.get("pg_kp_id"),
                        vector_score=0.0,
                        confidence=float(n.get("confidence") or 0.0),
                    ))

        # 去重 + 过滤低 conf + 限数量
        seen: set[str] = set()
        deduped: list[RetrievedNode] = []
        for n in out:
            if n.id in seen:
                continue
            if n.confidence < self.expand_min_confidence:
                continue
            seen.add(n.id)
            deduped.append(n)
        return deduped[:self.hop1_limit]

    # ----- PG 用户状态读取 -----

    async def _fetch_user_state(
        self, user_id: int, pg_kp_ids: list[int],
    ) -> dict[int, dict]:
        """从 PG user_kp_mastery 取 score。严格只读。"""
        if not pg_kp_ids:
            return {}
        async with async_session() as db:
            result = await db.execute(
                text("""
                    SELECT kp_id, score, correct_count, total_count
                    FROM user_kp_mastery
                    WHERE user_id = :uid AND kp_id = ANY(:kids)
                """),
                {"uid": user_id, "kids": pg_kp_ids},
            )
            rows = result.all()

        out: dict[int, dict] = {}
        for r in rows:
            correct = float(r.correct_count or 0)
            total = float(r.total_count or 0)
            score = float(r.score or 0.0)
            if score >= 0.8:
                status = "mastered"
            elif score >= 0.5:
                status = "in_progress"
            else:
                status = "weak"
            out[int(r.kp_id)] = {
                "score": score,
                "correct_rate": correct / max(total, 1.0),
                "status": status,
            }
        return out

    # ----- Fallback -----

    async def _fallback_answer(
        self, query: str, user_id: int,
    ) -> GraphRAGResult:
        """图谱没覆盖——拉 syllabus 节点 + 写 gap_questions。"""
        await self._log_gap(query, user_id)

        try:
            async with kg_session() as s:
                kps = await (await s.run("""
                    MATCH (c:Concept {type: 'KP'})
                    WHERE c.subject IN ['math-calc', 'math-linalg', 'math-prob']
                    RETURN c.id AS id, c.name AS name, c.type AS type
                    LIMIT 5
                """)).data()
        except Exception as e:
            logger.warning("fallback syllabus query failed: %s", e)
            kps = []

        return GraphRAGResult(
            answer="图谱暂未覆盖你的问题，以下是相关考点：",
            cited=[
                {"id": k["id"], "name": k["name"], "type": k["type"]}
                for k in kps
            ],
            seeds=[],
            expanded=[],
            used_token_estimate=100,
            fallback=True,
        )

    async def _log_gap(self, query: str, user_id: int) -> None:
        try:
            async with async_session() as db:
                await db.execute(
                    text("""
                        INSERT INTO gap_questions
                            (query, top_score, user_id, created_at)
                        VALUES (:q, 0.0, :u, now())
                    """),
                    {"q": query, "u": user_id},
                )
                await db.commit()
        except Exception as e:
            # gap log 失败不影响主流程
            logger.warning("log gap question failed: %s", e)

    # ----- 工具 -----

    async def _safe_embed(self, text_in: str) -> list[float]:
        """embedding 调用失败时返回空 list（触发 fallback）。"""
        try:
            emb = await self.embed_call(text_in)
            return emb or []
        except Exception as e:
            logger.warning("embed failed: %s", e)
            return []