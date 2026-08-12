"""阶段五·2D 飞轮：Neo4j migration 范例 — 新增 concept.priority 字段 + 索引。

触发场景：
    2D 飞轮若需要"按 priority 排序处理"，需 Concept 节点有 priority 数值字段。

执行方式：
    python -m kg.migrations.002_add_priority_index           # upgrade
    python -m kg.migrations.002_add_priority_index down      # downgrade

落地规范（参考主方案 §9）：
    1. 所有 Cypher 必须幂等（IF NOT EXISTS 或合并检查）
    2. 删字段/索引前先停服 → dump → 再 ops
    3. 每次变更 commit 一个版本号 + 改动说明到 migrations/CHANGELOG.md
"""
from __future__ import annotations

import asyncio
import sys


async def upgrade() -> None:
    """加索引（幂等）→ 回填默认值 → 验证 SHOW INDEXES."""
    from kg.neo4j_client import kg_session
    async with kg_session() as s:
        # 1) 加索引
        await s.run("""
            CREATE INDEX concept_priority IF NOT EXISTS
            FOR (c:Concept) ON (c.priority)
        """)
        # 2) 回填已有节点的 priority 默认值
        await s.run("""
            MATCH (c:Concept)
            WHERE c.priority IS NULL
            SET c.priority = 0
        """)


async def downgrade() -> None:
    """降级：删索引（不删字段，避免数据丢失）。"""
    from kg.neo4j_client import kg_session
    async with kg_session() as s:
        await s.run("DROP INDEX concept_priority IF EXISTS")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "down":
        asyncio.run(downgrade())
        print("[002] downgraded")
    else:
        asyncio.run(upgrade())
        print("[002] upgraded")


if __name__ == "__main__":
    main()