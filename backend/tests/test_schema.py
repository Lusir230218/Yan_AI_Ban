"""测试 v3 schema 完整性：所有表/列是否就位"""
import pytest
from sqlalchemy import text

from tests.conftest import _test_engine


@pytest.mark.asyncio
async def test_v3_tables_exist():
    """阶段二 v3 新增的 6 张表必须存在。"""
    expected = {
        "user_kp_mastery",
        "user_kp_weak",
        "mastery_snapshots",
        "mistake_categories",
        "user_mistakes",
        "mistake_occurs_in",
    }
    async with _test_engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
        """))).scalars().all()
    assert expected.issubset(set(rows)), f"缺失表: {expected - set(rows)}"


@pytest.mark.asyncio
async def test_kp_chapter_section_columns():
    """knowledge_points 加了 chapter / section。"""
    async with _test_engine.connect() as conn:
        cols = (await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'knowledge_points'
        """))).scalars().all()
    assert "chapter" in cols, "knowledge_points.chapter 缺失"
    assert "section" in cols, "knowledge_points.section 缺失"


@pytest.mark.asyncio
async def test_study_record_error_source_columns():
    """study_records 加了 error_category / source。"""
    async with _test_engine.connect() as conn:
        cols = (await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'study_records'
        """))).scalars().all()
    assert "error_category" in cols, "study_records.error_category 缺失"
    assert "source" in cols, "study_records.source 缺失"


@pytest.mark.asyncio
async def test_kp_backfill_chapter():
    """_ensure_columns 的回填：level=2 KP 必有 chapter 字段。"""
    async with _test_engine.connect() as conn:
        bad = (await conn.execute(text("""
            SELECT count(*) FROM knowledge_points
            WHERE level = 2 AND chapter IS NULL
        """))).scalar()
    assert bad == 0, f"level=2 KP 仍有 {bad} 行 chapter 为空"
