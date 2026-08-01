"""pytest fixtures: 真实 DB + AsyncClient + 测试用 user/KP/Question

测试不隔离 DB：每个测试用唯一 marker（test_<uuid>），跑完不清。
跑测试前需要：pip install pytest pytest-asyncio httpx

⚠️ 关键：用 NullPool 避免 pytest-asyncio 跨 event loop 时 asyncpg 连接复用问题
"""
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config import settings
from models.study import KnowledgePoint, Question
from models.user import User


# ── 独立测试引擎（NullPool：每操作新连接，无跨 loop 复用问题）──


_test_engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)
_test_session = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)


# ── DB / HTTP fixtures ──


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with _test_session() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    from main import app
    from core.database import get_db

    # 用 NullPool test engine 覆盖 FastAPI 的 get_db（避免跨 event loop 复用连接）
    async def _override_get_db():
        async with _test_session() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


# ── 隔离测试用 user ──


@pytest_asyncio.fixture
async def test_user(db: AsyncSession) -> User:
    marker = f"test_{uuid.uuid4().hex[:8]}"
    user = User(
        phone=marker,
        nickname=f"测试用户-{marker}",
        hashed_password="x",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_token(test_user: User) -> str:
    """给 test_user 签发一个能直接用的 JWT。"""
    from core.security import create_access_token
    return create_access_token({"sub": str(test_user.id)})


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient, auth_token: str) -> AsyncClient:
    client.headers["Authorization"] = f"Bearer {auth_token}"
    return client


# ── 隔离测试用 KP + Question ──


@pytest_asyncio.fixture
async def test_kp(db: AsyncSession) -> KnowledgePoint:
    marker = f"TEST-{uuid.uuid4().hex[:6]}"
    kp = KnowledgePoint(
        code=marker,
        name=f"测试KP-{marker}",
        subject="数学",
        level=2,
        sort_order=9999,
        chapter="测试章节",
    )
    db.add(kp)
    await db.commit()
    await db.refresh(kp)
    return kp


@pytest_asyncio.fixture
async def test_question(db: AsyncSession, test_kp: KnowledgePoint) -> Question:
    q = Question(
        question_type="choice",
        subject="数学",
        knowledge_point_id=test_kp.id,
        stem=f"测试题-{uuid.uuid4().hex[:6]}",
        options='["A. 对", "B. 错"]',
        correct_answer="A",
        difficulty=2,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return q
