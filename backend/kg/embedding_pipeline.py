"""Concept 节点入库后异步算 embedding。与 extract 解耦：失败不影响主流程。

Embedding API 复用阶段一 OpenAI proxy（text-embedding-3-small / 1536 维）。
详见 memory/stage5-llm-choice.md。
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from config import settings
from kg.neo4j_client import kg_session


async def enqueue_embedding_job(batch_size: int = 50) -> int:
    """找出没 embedding 的节点，分批调 embedding API。

    Returns 处理的节点数。
    """
    async with kg_session() as s:
        rows = await (await s.run("""
            MATCH (c:Concept)
            WHERE c.embedding IS NULL AND c.status = 'active'
            RETURN c.id AS id, c.name AS name, c.aliases AS aliases,
                   c.definition AS definition
            LIMIT $batch_size
        """, batch_size=batch_size)).data()

    if not rows:
        return 0

    for r in rows:
        try:
            emb = await embed_text(_compose_text(r))
            await _write_embedding(r["id"], emb)
        except Exception as e:
            # 单点失败不影响其他节点
            print(f"[embedding] skip {r['id']}: {e}")
    return len(rows)


def _compose_text(node: dict[str, Any]) -> str:
    """name + aliases + definition 前 200 字拼成 embedding 输入。"""
    parts = [node["name"]]
    if node.get("aliases"):
        parts.append(" / ".join(node["aliases"]))
    if node.get("definition"):
        parts.append(node["definition"][:200])
    return " — ".join(parts)


async def embed_text(text: str) -> list[float]:
    """调 OpenAI 兼容 embedding API（复用阶段一 proxy）。public wrapper
    让 graph_rag 等模块可以合法引用。
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.LLM_BASE_URL}/embeddings",
            headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
            json={"model": settings.EMBEDDING_MODEL, "input": text},
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]


# 私有别名 — 保留以便不破坏 extract.py 等历史调用方
_embed_text = embed_text


async def _write_embedding(concept_id: str, embedding: list[float]) -> None:
    """写回 Concept.embedding + embedding_model + embedded_at。"""
    async with kg_session() as s:
        await s.run("""
            MATCH (c:Concept {id: $id})
            SET c.embedding = $emb,
                c.embedding_model = $model,
                c.embedded_at = datetime()
        """, id=concept_id, emb=embedding, model=settings.EMBEDDING_MODEL)


async def run_worker(stop_after_idle_sec: int = 60) -> None:
    """长跑 worker，空闲 N 秒后退出。可被 cron / 队列触发。"""
    while True:
        processed = await enqueue_embedding_job()
        if processed == 0:
            await asyncio.sleep(stop_after_idle_sec)
            return