"""Neo4j 知识图谱 Schema 定义与初始化"""

from neo4j import AsyncDriver


CONSTRAINTS = [
    "CREATE CONSTRAINT subject_name IF NOT EXISTS FOR (s:Subject) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT chapter_name IF NOT EXISTS FOR (c:Chapter) REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT section_name IF NOT EXISTS FOR (s:Section) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT kp_name IF NOT EXISTS FOR (k:KnowledgePoint) REQUIRE k.name IS UNIQUE",
    "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
]


SEED_SUBJECTS = [
    {
        "name": "数学",
        "chapters": [
            {
                "name": "高等数学",
                "sections": [
                    {"name": "函数与极限"},
                    {"name": "导数与微分"},
                    {"name": "不定积分"},
                    {"name": "定积分"},
                ],
            },
            {"name": "线性代数", "sections": [{"name": "行列式"}, {"name": "矩阵"}]},
            {
                "name": "概率论与数理统计",
                "sections": [{"name": "随机事件与概率"}, {"name": "随机变量及其分布"}],
            },
        ],
    },
    {
        "name": "英语",
        "chapters": [
            {"name": "完形填空", "sections": [{"name": "词汇辨析"}, {"name": "语法逻辑"}]},
            {"name": "阅读理解", "sections": [{"name": "主旨大意"}, {"name": "细节理解"}]},
            {"name": "写作", "sections": [{"name": "小作文"}, {"name": "大作文"}]},
        ],
    },
    {
        "name": "政治",
        "chapters": [
            {"name": "马克思主义基本原理", "sections": [{"name": "唯物论"}, {"name": "辩证法"}]},
            {"name": "毛泽东思想和中国特色社会主义理论体系概论", "sections": [{"name": "毛泽东思想"}, {"name": "邓小平理论"}]},
        ],
    },
]


async def init_schema(driver: AsyncDriver) -> None:
    """创建约束和索引"""
    async with driver.session() as session:
        for cql in CONSTRAINTS:
            await session.run(cql)


async def seed_knowledge_graph(driver: AsyncDriver) -> None:
    """插入考研大纲知识图谱骨架"""
    async with driver.session() as session:
        for subject in SEED_SUBJECTS:
            await session.run(
                "MERGE (s:Subject {name: $name}) RETURN s", name=subject["name"]
            )
            for chapter in subject.get("chapters", []):
                await session.run(
                    """
                    MATCH (s:Subject {name: $subject})
                    MERGE (c:Chapter {name: $chapter})
                    MERGE (s)-[:HAS_CHAPTER]->(c)
                    """,
                    subject=subject["name"],
                    chapter=chapter["name"],
                )
                for section in chapter.get("sections", []):
                    await session.run(
                        """
                        MATCH (c:Chapter {name: $chapter})
                        MERGE (sec:Section {name: $section})
                        MERGE (c)-[:HAS_SECTION]->(sec)
                        """,
                        chapter=chapter["name"],
                        section=section["name"],
                    )
