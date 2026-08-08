import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from config import settings
from core.database import engine, Base
from api.v1.router import router as v1_router
from jobs.snapshot_mastery import snapshot_cron_loop

logger = logging.getLogger("main")


async def _ensure_columns(conn):
    """Base.metadata.create_all 不会给已有表加列；这里幂等 ALTER。
    阶段二 v3 新加列。"""
    # knowledge_points 加 chapter / section
    await conn.execute(text(
        "ALTER TABLE knowledge_points ADD COLUMN IF NOT EXISTS chapter VARCHAR(100)"
    ))
    await conn.execute(text(
        "ALTER TABLE knowledge_points ADD COLUMN IF NOT EXISTS section VARCHAR(100)"
    ))
    # 回填：level=2 KP → chapter = 自身 name
    await conn.execute(text("""
        UPDATE knowledge_points
        SET chapter = name
        WHERE level = 2 AND chapter IS NULL
    """))
    # 回填：level=3 KP → chapter = parent.name, section = 自身 name
    await conn.execute(text("""
        UPDATE knowledge_points k
        SET chapter = p.name,
            section = k.name
        FROM knowledge_points p
        WHERE k.parent_id = p.id
          AND k.level = 3
          AND k.chapter IS NULL
    """))
    # study_records 加 error_category / source
    await conn.execute(text(
        "ALTER TABLE study_records ADD COLUMN IF NOT EXISTS error_category VARCHAR(64)"
    ))
    await conn.execute(text(
        "ALTER TABLE study_records ADD COLUMN IF NOT EXISTS source VARCHAR(10) DEFAULT 'human'"
    ))


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_columns(conn)
    cron_task = asyncio.create_task(snapshot_cron_loop(hour=settings.SNAPSHOT_CRON_HOUR))
    logger.info("snapshot_cron started")
    # 阶段五·2A: 启动 Neo4j + apply kg schema (仅 dev/staging)
    if settings.KG_ENV != "production":
        from kg.neo4j_client import get_kg_driver
        from kg.schema import init_kg_schema
        await get_kg_driver()
        await init_kg_schema(embedding_dim=settings.EMBEDDING_DIM)
        logger.info("[kg] schema applied (KG_ENV=%s)", settings.KG_ENV)
    yield
    cron_task.cancel()
    if settings.KG_ENV != "production":
        from kg.neo4j_client import close_kg_driver
        await close_kg_driver()


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.get("/")
async def root():
    return {"message": "研AI伴 API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", reload=True)
