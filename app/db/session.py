from app.db.database import async_session_maker

from collections.abc import AsyncGenerator


async def get_session() -> AsyncGenerator:
    async with async_session_maker() as session:
        yield session