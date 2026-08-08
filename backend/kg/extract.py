"""阶段五·2B 抽取 pipeline 主控。

CLI:
    python -m kg extract --source textbook:tongji-gaoshux7 --docx-path X.docx [--chunks-dir DIR]
    python -m kg extract --source syllabus:math        --docx-path X.json   (大纲 JSON)

流程:
    docx → parse_docx → to_chunk_files 落盘
         → read_chunk_files 读回
         → per-chunk: 召回 → LLM 抽 → 校验(3 轮重试) → 5 防线后处理 → MERGE 落库
    全部 chunks 跑完后:
         merge_duplicates() + enqueue_embedding_job()
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from sqlalchemy import text

from config import settings
from kg.docx_parser import (
    Chunk, parse_docx, to_chunk_files, read_chunk_files,
)
from kg.embedding_pipeline import enqueue_embedding_job
from kg.llm_client import chat_json, LLMError
from kg.merge_dups import merge_duplicates
from kg.neo4j_client import kg_session
from kg.ontology import (
    ConceptType, RelationType, validate_extraction_payload,
    type_from_id,
)
from kg.prompts import TEXTBOOK_EXTRACT_PROMPT, RETRY_PROMPT_TAIL
from kg.syllabus_loader import load_syllabus


# ===================== CLI =====================
def cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("kg.extract")
    p.add_argument("--source", required=True,
                   help="textbook:tongji-gaoshux7 或 syllabus:math")
    p.add_argument("--docx-path", help="教材 docx 路径（仅 textbook 源）")
    p.add_argument("--chunks-dir",
                   help="chunk 落盘目录（默认 data/processed/<source-stem>）")
    p.add_argument("--syllabus-path", help="大纲 JSON 路径（仅 syllabus 源）")
    p.add_argument("--max-chunks", type=int, default=200)
    p.add_argument("--incremental", action="store_true",
                   help="只跑 source_ref 未见过的 chunk")
    p.add_argument("--subject", default="math-calc")
    p.add_argument("--review-queue", action="store_true",
                   help="只列低 confidence 候选，不写入")
    p.add_argument("--approve-id", help="批准候选")
    p.add_argument("--reject-id", help="拒绝候选")
    return p


# ===================== 主流程 =====================
async def run(source: str, docx_path: str | None, max_chunks: int,
              incremental: bool, subject: str,
              chunks_output_dir: str | Path | None = None) -> dict:
    """主入口。返回统计 {concepts, relations, errors, low_conf_skipped}。"""
    if source.startswith("syllabus:"):
        n = await load_syllabus(docx_path)
        return {"mode": "syllabus", "loaded": n}

    # textbook 模式: parse docx → 落盘 chunks/* + index.json → 读回 → LLM 循环
    raw_chunks = parse_docx(docx_path)
    chunks_dir = Path(chunks_output_dir or f"data/processed/{Path(docx_path).stem}")
    index_path = to_chunk_files(raw_chunks, chunks_dir,
                                source=source, subject=subject)
    chunks = read_chunk_files(index_path)

    if incremental:
        seen = await _fetch_seen_chunk_ids(source)
        chunks = [c for c in chunks if c.chunk_id not in seen]
    chunks = chunks[:max_chunks]

    stats = {"concepts": 0, "relations": 0, "errors": 0,
             "low_conf_skipped": 0, "chunks_processed": 0}

    for chunk in chunks:
        try:
            existing = await _fetch_related_concepts(chunk.text, subject)
            payload = await _extract_one_chunk(chunk, subject, existing)
            await _persist_extraction(payload, source=source,
                                       source_ref=chunk.chunk_id,
                                       subject=subject)
            stats["concepts"] += len(payload.get("concepts", []))
            stats["relations"] += len(payload.get("relations", []))
            stats["chunks_processed"] += 1
            await _mark_chunk_seen(source, chunk.chunk_id)
        except LLMError as e:
            stats["errors"] += 1
            print(f"[error] chunk {chunk.chunk_id}: {e}")
        except Exception as e:
            stats["errors"] += 1
            print(f"[error] chunk {chunk.chunk_id}: {e}")

    await merge_duplicates()
    await enqueue_embedding_job()
    return stats


async def _extract_one_chunk(
    chunk: Chunk, subject: str, existing: list[dict],
) -> dict[str, Any]:
    """LLM 抽 + ontology 校验 + 最多 3 轮重试。"""
    existing_json = json.dumps(
        [{"id": c["id"], "name": c["name"], "type": c["type"]} for c in existing],
        ensure_ascii=False,
    )
    base_prompt = TEXTBOOK_EXTRACT_PROMPT.format(
        existing_concepts_json=existing_json or "（暂无）",
        text_chunk=chunk.text,
        subject=subject,
    )

    errors: list[str] = []
    last_result: dict[str, Any] = {}
    for attempt in range(3):
        prompt = base_prompt
        if errors:
            prompt += RETRY_PROMPT_TAIL.format(errors="\n".join(errors))
        try:
            result = await chat_json(prompt)
            last_result = result
        except LLMError as e:
            if attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)
            continue

        existing_ids = {c["id"] for c in existing}
        errors = validate_extraction_payload(
            result,
            existing_concept_ids=existing_ids,
        )
        if not errors:
            return result
    # 3 轮都失败 → 入候选表
    await _save_chunk_candidate(chunk, last_result, errors)
    return {"concepts": [], "relations": []}


async def _fetch_related_concepts(text: str, subject: str, top_k: int = 10) -> list[dict]:
    """向量召回 top-K 已有概念（subject 过滤）。"""
    try:
        emb = await _embed(text)
    except Exception:
        return []
    async with kg_session() as s:
        rows = await (await s.run("""
            CALL db.index.vector.queryNodes('concept_embedding', $k, $emb)
            YIELD node AS c, score
            WHERE c.embedding_model = $model
              AND (c.subject = $subject OR c.subject = 'unknown')
            RETURN c.id AS id, c.name AS name, c.type AS type,
                   c.subject AS subject
            ORDER BY score DESC
            LIMIT $k
        """, k=top_k, emb=emb, model=settings.EMBEDDING_MODEL,
             subject=subject)).data()
    return rows


async def _embed(text: str) -> list[float]:
    """单条文本调 embedding API。"""
    import httpx
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.LLM_BASE_URL}/embeddings",
            headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
            json={"model": settings.EMBEDDING_MODEL, "input": text},
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]


async def _persist_extraction(
    payload: dict, source: str, source_ref: str, subject: str,
) -> None:
    """5 道防线 + MERGE 落库。"""
    concepts = payload.get("concepts", [])
    relations = payload.get("relations", [])

    existing_lookup = await _fetch_existing_by_typename(concepts)
    existing_rels = await _fetch_existing_rels(relations)

    processed_rels = []
    for r in relations:
        if r["from"] == r["to"]:
            continue
        from_subj, to_subj = await _get_subjects(r["from"], r["to"])
        is_cross = (from_subj and to_subj and from_subj != to_subj
                    and from_subj != "unknown" and to_subj != "unknown")
        r["confidence"] = max(
            r.get("confidence", 0.5),
            settings.CROSS_SUBJECT_INITIAL_CONFIDENCE if is_cross
            else settings.INITIAL_CONFIDENCE,
        )
        r["_cross_subject"] = is_cross
        processed_rels.append(r)

    rel_set = {(r["from"], r["rel"]) for r in processed_rels}
    for r in processed_rels:
        if (r["to"], r["rel"]) in rel_set and (r["to"], r["rel"]) != (r["from"], r["rel"]):
            r["disputed"] = True

    for r in processed_rels[:]:
        if r["confidence"] < 0.5:
            await _save_rel_candidate(r, source)
            processed_rels.remove(r)

    async with kg_session() as s:
        for c in concepts:
            existing = existing_lookup.get((c.get("name", ""), c.get("type", "")))
            final_id = existing["id"] if existing else c["id"]
            await s.run("""
                MERGE (n:Concept {id: $id})
                ON CREATE SET
                    n.name         = $name,
                    n.type         = $type,
                    n.aliases      = $aliases,
                    n.definition   = $definition,
                    n.difficulty   = $difficulty,
                    n.level        = $level,
                    n.subject      = $subject,
                    n.confidence   = $conf,
                    n.source       = $source,
                    n.source_ref   = $source_ref,
                    n.status       = 'active',
                    n.created_at   = datetime()
                ON MATCH SET
                    n.aliases      = [x IN coalesce(n.aliases, []) + $aliases WHERE x IS NOT NULL],
                    n.updated_at   = datetime()
            """, id=final_id, name=c.get("name", ""), type=c.get("type", "Method"),
                 aliases=c.get("aliases", []),
                 definition=c.get("definition"),
                 difficulty=c.get("difficulty", 0.5),
                 level=c.get("level", 2),
                 subject=c.get("subject", subject),
                 conf=c.get("confidence", 0.5),
                 source=source, source_ref=source_ref)

        for r in processed_rels:
            is_existing = (r["from"], r["rel"], r["to"]) in existing_rels
            if is_existing:
                await s.run(f"""
                    MATCH (a:Concept {{id: $from}}), (b:Concept {{id: $to}})
                    MATCH (a)-[rel:{r["rel"]}]->(b)
                    SET rel.confidence = (rel.confidence + $conf) / 2,
                        rel.updated_at = datetime()
                """, **{"from": r["from"], "to": r["to"], "conf": r["confidence"]})
            else:
                await s.run(f"""
                    MATCH (a:Concept {{id: $from}}), (b:Concept {{id: $to}})
                    MERGE (a)-[rel:{r["rel"]}]->(b)
                    ON CREATE SET
                        rel.confidence = $conf,
                        rel.disputed   = $disputed,
                        rel.source     = $source,
                        rel.source_ref = $source_ref,
                        rel.created_at = datetime()
                """, **{"from": r["from"], "to": r["to"],
                       "conf": r["confidence"],
                       "disputed": r.get("disputed", False),
                       "source": source, "source_ref": source_ref})


async def _fetch_existing_by_typename(concepts: list[dict]) -> dict:
    """查同 (type, name) 已存在的节点 id。"""
    names = [c.get("name", "") for c in concepts if c.get("name")]
    types = [c.get("type", "") for c in concepts if c.get("type")]
    if not names or not types:
        return {}
    async with kg_session() as s:
        rows = await (await s.run("""
            MATCH (c:Concept)
            WHERE c.name IN $names AND c.type IN $types
            RETURN c.id AS id, c.name AS name, c.type AS type
        """, names=names, types=types)).data()
    return {(r["name"], r["type"]): {"id": r["id"]} for r in rows}


async def _fetch_existing_rels(relations: list[dict]) -> set:
    """查已有 (from, rel, to) 三元组集合。"""
    if not relations:
        return set()
    froms = list({r["from"] for r in relations})
    tos = list({r["to"] for r in relations})
    async with kg_session() as s:
        rows = await (await s.run("""
            MATCH (a:Concept)-[r]->(b:Concept)
            WHERE a.id IN $froms AND b.id IN $tos
            RETURN a.id AS from, type(r) AS rel, b.id AS to
        """, froms=froms, tos=tos)).data()
    return {(r["from"], r["rel"], r["to"]) for r in rows}


async def _get_subjects(*ids: str) -> list[str | None]:
    async with kg_session() as s:
        rows = await (await s.run("""
            MATCH (c:Concept)
            WHERE c.id IN $ids
            RETURN c.id AS id, c.subject AS subject
        """, ids=list(ids))).data()
    m = {r["id"]: r["subject"] for r in rows}
    return [m.get(i) for i in ids]


async def _fetch_seen_chunk_ids(source: str) -> set[str]:
    from core.database import async_session
    async with async_session() as db:
        rows = (await db.execute(text("""
            SELECT payload->>'chunk_id' AS chunk_id
            FROM kg_extraction_candidates
            WHERE kind = 'chunk_seen' AND payload->>'source' = :s
        """), {"s": source})).all()
    return {r[0] for r in rows if r[0]}


async def _mark_chunk_seen(source: str, chunk_id: str) -> None:
    from core.database import async_session
    async with async_session() as db:
        await db.execute(text("""
            INSERT INTO kg_extraction_candidates
                (kind, payload, status, created_at)
            VALUES
                ('chunk_seen', CAST(:payload AS JSONB), 'done', now())
        """), {"payload": json.dumps({"source": source, "chunk_id": chunk_id})})


async def _save_chunk_candidate(chunk: Chunk, payload: dict, errors: list[str]) -> None:
    from core.database import async_session
    async with async_session() as db:
        await db.execute(text("""
            INSERT INTO kg_extraction_candidates
                (kind, payload, status, created_at)
            VALUES
                ('unresolved_chunk', CAST(:payload AS JSONB), 'pending', now())
        """), {"payload": json.dumps({
            "chunk_id": chunk.chunk_id,
            "errors": errors[:5],
        })})


async def _save_rel_candidate(rel: dict, source: str) -> None:
    from core.database import async_session
    async with async_session() as db:
        await db.execute(text("""
            INSERT INTO kg_extraction_candidates
                (kind, payload, status, created_at)
            VALUES
                ('low_conf_relation', CAST(:payload AS JSONB), 'pending', now())
        """), {"payload": json.dumps({
            "from": rel["from"], "rel": rel["rel"], "to": rel["to"],
            "confidence": rel["confidence"], "source": source,
            "cross_subject": rel.get("_cross_subject", False),
        })})


# ===================== 入口 =====================
if __name__ == "__main__":
    args = cli().parse_args()
    if args.review_queue:
        from kg.extract_admin import show_review_queue
        asyncio.run(show_review_queue())
    elif args.approve_id:
        from kg.extract_admin import approve_candidate
        asyncio.run(approve_candidate(args.approve_id))
    elif args.reject_id:
        from kg.extract_admin import reject_candidate
        asyncio.run(reject_candidate(args.reject_id))
    else:
        stats = asyncio.run(run(
            source=args.source,
            docx_path=args.docx_path or args.syllabus_path,
            max_chunks=args.max_chunks,
            incremental=args.incremental,
            subject=args.subject,
            chunks_output_dir=args.chunks_dir,
        ))
        print(stats)