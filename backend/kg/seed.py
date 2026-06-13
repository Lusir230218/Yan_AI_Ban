"""知识图谱初始化脚本 — python -m kg.seed"""
import asyncio

from kg.neo4j_client import get_kg_driver, close_kg_driver
from kg.schema import init_schema, seed_knowledge_graph


async def main():
    driver = await get_kg_driver()
    print("Neo4j 已连接")
    await init_schema(driver)
    print("约束创建完成")
    await seed_knowledge_graph(driver)
    print("考研大纲骨架写入完成")
    await close_kg_driver()


if __name__ == "__main__":
    asyncio.run(main())
