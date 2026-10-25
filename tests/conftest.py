import os

import pytest_asyncio
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.rate_limit import RateLimiter, get_login_limiter
from app.db.base import Base
from app.db.session import get_session
from app.main import app

load_dotenv(".env.test")

TEST_DB_URL = URL.create(
    drivername="postgresql+asyncpg",
    username=os.environ["TESTS_POSTGRES_USER"],
    password=os.environ["TESTS_POSTGRES_PASSWORD"],
    host=os.environ["TESTS_POSTGRES_HOST"],
    port=int(os.environ["TESTS_POSTGRES_PORT"]),
    database=os.environ["TESTS_POSTGRES_NAME"],
)

assert "test" in TEST_DB_URL.database, "Refusing to run on non-test DB"


@pytest_asyncio.fixture(scope="session")
async def engine():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine):
    async with engine.connect() as conn:
        trans = await conn.begin()
        async with AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as s:
            yield s
        await trans.rollback()


class InMemoryRedis:
    """The few Redis commands RateLimiter uses, without a Redis server."""

    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return None
        self.values[key] = int(value)
        self.ttls[key] = ex if ex is not None else -1
        return True

    async def incr(self, key):
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def ttl(self, key):
        return self.ttls.get(key, -2)


@pytest_asyncio.fixture
async def login_limiter():
    """Fresh limiter per test with the real limits; tests may change .limit."""
    return RateLimiter(
        InMemoryRedis(),
        scope="login",
        limit=settings.LOGIN_RATE_LIMIT,
        window_seconds=settings.LOGIN_RATE_WINDOW_SECONDS,
    )


@pytest_asyncio.fixture
async def client(session, login_limiter):
    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_login_limiter] = lambda: login_limiter
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()