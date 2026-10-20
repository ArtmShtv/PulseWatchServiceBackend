import os

import pytest_asyncio
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

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


@pytest_asyncio.fixture
async def client(session):
    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()