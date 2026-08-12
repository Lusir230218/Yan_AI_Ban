"""阶段五·2D 飞轮：admin 手工维护 — 概念合并 / 归档 / 还原。

与 kg/merge_dups.py 的区别：
- merge_dups.py   自动按 (type, name) 严格相等批量合并（抽取后兜底）
- admin_concepts  admin 手工调用，处理同义异名 / 错误归档等需要人决策的场景

所有操作写审计字段（merged_by / archived_by），便于事后追溯。
"""
from __future__ import annotations

from kg.neo4j_client import kg_session


async def merge_concepts(keep_id: str, drop_id: str,
                         admin_user_id: int) -> dict:
    """合并两个 Concept：所有边接到 keep，drop 删除。

    使用 APOC mergeNodes（如果 Neo4j 装了 APOC），失败则 fallback 到手工
    OPTIONAL MATCH + DETACH DELETE — 与 kg/merge_dups._merge_nodes 一致。

    注意：APOC mergeNodes 不可逆；只能 restore archived 节点。
    """
    async with kg_session() as s:
        try:
            await s.run("""
                MATCH (keep:Concept {id: $keep}), (drop:Concept {id: $drop})
                CALL apoc.refactor.mergeNodes([keep, drop], {
                    properties: 'combine', mergeRels: true
                }) YIELD node
                SET node.merged_from = coalesce(node.merged_from, []) + $drop,
                    node.merged_at = datetime(),
                    node.merged_by = $admin
                RETURN node.id AS id
            """, keep=keep_id, drop=drop_id, admin=admin_user_id)
        except Exception:
            # fallback: 手工 OPTIONAL MATCH + DETACH DELETE（保留边方向语义）
            await s.run("""
                MATCH (keep:Concept {id: $keep}), (drop:Concept {id: $drop})
                OPTIONAL MATCH (drop)-[r_out]->(other)
                OPTIONAL MATCH (other)-[r_in]->(drop)
                WITH keep, drop, r_out, r_in, other
                FOREACH (_ IN CASE WHEN r_out IS NULL THEN [] ELSE [1] END |
                    MERGE (keep)-[rnew:SAME_AS]->(other))
                FOREACH (_ IN CASE WHEN r_in IS NULL THEN [] ELSE [1] END |
                    MERGE (other)-[rnew2:SAME_AS]->(keep))
                SET keep.merged_from = coalesce(keep.merged_from, []) + $drop,
                    keep.merged_at = datetime(),
                    keep.merged_by = $admin
                WITH drop
                DETACH DELETE drop
            """, keep=keep_id, drop=drop_id, admin=admin_user_id)
    return {"merged": keep_id, "from": drop_id}


async def archive_concept(concept_id: str, admin_user_id: int) -> dict:
    """归档：c.status = 'archived'。节点仍在，关系不删，但 graph_rag 会按 status='active' 过滤。"""
    async with kg_session() as s:
        await s.run("""
            MATCH (c:Concept {id: $id})
            SET c.status = 'archived',
                c.archived_at = datetime(),
                c.archived_by = $admin
        """, id=concept_id, admin=admin_user_id)
    return {"archived": concept_id}


async def restore_concept(concept_id: str) -> dict:
    """还原归档：c.status = 'active'，清掉 archived_* 字段。"""
    async with kg_session() as s:
        await s.run("""
            MATCH (c:Concept {id: $id})
            SET c.status = 'active',
                c.archived_at = null,
                c.archived_by = null
        """, id=concept_id)
    return {"restored": concept_id}