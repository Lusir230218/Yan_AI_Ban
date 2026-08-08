"""抽取后跑一次：同名同 type 合并 / 同名不同 type 标候选。

merge_dups 是 2B 兜底——LLM 偶尔造同义异名节点（"换元积分法"和"换元法"），按 (type, name) 严格相等合并。
"""
from __future__ import annotations

import json
from sqlalchemy import text

from core.database import async_session
from kg.neo4j_client import kg_session


async def merge_duplicates() -> int:
    """找同 (type, name) 出现多次的节点，保留字典序最短 id，合并其他。"""
    async with kg_session() as s:
        dups = await (await s.run("""
            MATCH (c:Concept)
            WITH c.type AS type, c.name AS name, collect(c) AS nodes
            WHERE size(nodes) > 1
            RETURN type, name, [n IN nodes | n.id] AS ids
        """)).data()

    merged = 0
    for d in dups:
        ids = sorted(d["ids"])  # 字典序，留 id 最短的
        keep = ids[0]
        drop_list = ids[1:]
        if drop_list:
            await _merge_nodes(keep, drop_list)
            merged += len(drop_list)
    return merged


async def _merge_nodes(keep_id: str, drop_ids: list[str]) -> None:
    """把 drop_ids 的所有边接到 keep_id，然后 detach delete drop_ids。

    使用 APOC mergeNodes（如果 Neo4j 装了 APOC），否则手工 OPTIONAL MATCH + MERGE。
    """
    async with kg_session() as s:
        for drop_id in drop_ids:
            try:
                await s.run("""
                    MATCH (keep:Concept {id: $keep}), (drop:Concept {id: $drop})
                    CALL apoc.refactor.mergeNodes([keep, drop], {
                        properties: 'combine', mergeRels: true
                    }) YIELD node
                    SET node.merged_from = coalesce(node.merged_from, []) + $drop
                    RETURN node.id AS id
                """, keep=keep_id, drop=drop_id)
            except Exception:
                # 降级：手工 OPTIONAL MATCH + MERGE + DETACH DELETE
                await s.run("""
                    MATCH (keep:Concept {id: $keep}), (drop:Concept {id: $drop})
                    OPTIONAL MATCH (drop)-[r_out]->()
                    OPTIONAL MATCH ()-[r_in]->(drop)
                    WITH keep, drop,
                         collect(DISTINCT {src: startNode(r_in), rel: type(r_in), dst: keep}) AS in_edges,
                         collect(DISTINCT {src: keep, rel: type(r_out), dst: endNode(r_out)}) AS out_edges
                    FOREACH (e IN in_edges |
                        MERGE (src:Concept {id: e.src.id})
                        MERGE (src)-[rnew:SAME_AS]->(keep))
                    FOREACH (e IN out_edges |
                        MERGE (keep)-[rnew2:SAME_AS]->(dst:Concept {id: e.dst.id}))
                    DETACH DELETE drop
                """, keep=keep_id, drop=drop_id)


async def save_conflict_to_candidates(name: str, type_a: str, type_b: str, ids: list[str]) -> None:
    """同名不同 type 入候选表，人工 review 决定归到哪个 type。"""
    async with async_session() as db:
        await db.execute(text("""
            INSERT INTO kg_extraction_candidates
                (kind, payload, status, created_at)
            VALUES
                ('concept_conflict', CAST(:payload AS JSONB), 'pending', now())
        """), {"payload": json.dumps({
            "name": name, "types": list({type_a, type_b}), "ids": ids,
        })})