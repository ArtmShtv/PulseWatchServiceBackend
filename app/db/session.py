from collections.abc import AsyncGenerator

from app.db.database import async_session_maker


async def get_session() -> AsyncGenerator:
    async with async_session_maker() as session:
        yield session