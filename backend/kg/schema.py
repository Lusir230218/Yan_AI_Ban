"""Neo4j 约束 / 索引。约束和向量索引都在这里声明，由 init_kg_schema() 幂等执行。"""
from __future__ import annotations

import os

from kg.neo4j_client import kg_session


# ============= 约束 =============
CONSTRAINTS: list[str] = [
    "CREATE CONSTRAINT concept_id IF NOT EXISTS "
    "FOR (c:Concept) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT concept_type_name IF NOT EXISTS "
    "FOR (c:Concept) REQUIRE (c.type, c.name) IS NODE KEY",
]


# ============= 索引 =============
INDEXES: list[str] = [
    "CREATE INDEX concept_type IF NOT EXISTS "
    "FOR (c:Concept) ON (c.type)",
    "CREATE INDEX concept_confidence IF NOT EXISTS "
    "FOR (c:Concept) ON (c.confidence)",
    "CREATE INDEX concept_status IF NOT EXISTS "
    "FOR (c:Concept) ON (c.status)",
    "CREATE INDEX concept_subject IF NOT EXISTS "
    "FOR (c:Concept) ON (c.subject)",
    "CREATE FULLTEXT INDEX concept_search IF NOT EXISTS "
    "FOR (c:Concept) ON EACH [c.name, c.aliases, c.definition]",
]


def vector_index_statement(dim: int) -> str:
    """向量索引。维度由 EMBEDDING_DIM 配置决定。"""
    return (
        "CREATE VECTOR INDEX concept_embedding IF NOT EXISTS "
        "FOR (c:Concept) ON (c.embedding) "
        "OPTIONS {indexConfig: {"
        "  `vector.dimensions`: $dim, "
        "  `vector.similarity_function`: 'cosine'"
        "}}"
    )


async def init_kg_schema(embedding_dim: int) -> None:
    """幂等地 apply 全部约束 + 索引 + 向量索引。

    生产环境**短路**——schema 变更走独立 migration 流程（2D 提供范例）。
    """
    if os.getenv("KG_ENV", "production") == "production":
        return
    async with kg_session() as s:
        for stmt in CONSTRAINTS + INDEXES:
            await s.run(stmt)
        await s.run(vector_index_statement(embedding_dim), dim=embedding_dim)


async def drop_kg_schema() -> None:
    """**仅 dev**。删约束/索引（节点不动）。"""
    if os.getenv("KG_ENV", "production") != "dev":
        raise RuntimeError("drop_kg_schema 仅 dev 环境允许")
    async with kg_session() as s:
        for stmt in reversed(INDEXES + CONSTRAINTS):
            drop_stmt = stmt.replace("CREATE", "DROP").replace(" IF NOT EXISTS", "")
            await s.run(drop_stmt)


async def list_constraints_and_indexes() -> dict:
    """调试 / 测试用：SHOW CONSTRAINTS + SHOW INDEXES 返回的 name 列表。"""
    async with kg_session() as s:
        consts = await (await s.run("SHOW CONSTRAINTS")).data()
        idxs   = await (await s.run("SHOW INDEXES")).data()
    return {
        "constraints": [c.get("name") for c in consts],
        "indexes":     [i.get("name") for i in idxs],
    }
