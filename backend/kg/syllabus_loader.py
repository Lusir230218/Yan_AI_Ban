"""大纲 → KP 节点直入 Neo4j（不走 LLM）。

大纲是教育部审定版 = 权威信源，confidence 起点 0.7。
每个 KP 反查 PG knowledge_points.code 拿 pg_kp_id。
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from kg.neo4j_client import kg_session


async def load_syllabus(json_path: str | Path) -> int:
    """从 JSON 读大纲 → 直接写 Neo4j KP 节点（不走 LLM）。返回写入数。"""
    items = json.loads(Path(json_path).read_text(encoding="utf-8"))
    pg_kp_id_map = await _fetch_pg_kp_id_map()

    written = 0
    async with kg_session() as s:
        for item in items:
            pg_id = pg_kp_id_map.get(item["code"])
            if not pg_id:
                print(f"[warn] {item['code']} 未在 PG knowledge_points 找到, 跳过")
                continue
            await s.run("""
                MERGE (c:Concept {id: $id})
                SET c.name         = $name,
                    c.type         = 'KP',
                    c.subject      = $subject,
                    c.pg_kp_id     = $pg_id,
                    c.level        = $level,
                    c.chapter      = $chapter,
                    c.section      = $section,
                    c.confidence   = 0.7,
                    c.source       = 'syllabus:' + $subject,
                    c.source_ref   = $code,
                    c.status       = 'active',
                    c.created_at   = coalesce(c.created_at, datetime()),
                    c.updated_at   = datetime()
            """, id=f"kp:{item['code']}", name=item["name"],
                 subject=item["subject"], pg_id=pg_id, level=item["level"],
                 chapter=item.get("chapter"), section=item.get("section"),
                 code=item["code"])
            written += 1
    return written


async def _fetch_pg_kp_id_map() -> dict[str, int]:
    """查 PG knowledge_points.code → id 的映射。"""
    from core.database import async_session

    async with async_session() as db:
        rows = (await db.execute(text(
            "SELECT id, code FROM knowledge_points"
        ))).all()
    return {r.code: r.id for r in rows}