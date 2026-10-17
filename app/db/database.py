from datetime import UTC, datetime
from typing import Annotated

from sqlalchemy import DateTime, func
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import mapped_column

from app.core.config import get_db_url

POSTGRES_URL = get_db_url()


int_pk = Annotated[
    int, 
    mapped_column(primary_key=True)
]
created_at = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), server_default=func.now()),
]
updated_at = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    ),
]


engine = create_async_engine(
    POSTGRES_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False
)
