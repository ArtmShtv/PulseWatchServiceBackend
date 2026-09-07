from datetime import datetime
from typing import Annotated

from sqlalchemy import func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import mapped_column

from app.core.config import get_db_url


POSTGRES_URL = get_db_url()


int_pk = Annotated[
    int, 
    mapped_column(primary_key=True)
]
created_at = Annotated[
    datetime,
    mapped_column(server_default=func.now())
]
updated_at = Annotated[
    datetime,
    mapped_column(
        server_default=func.now(),
        onupdate=datetime.now
    )
]


engine = create_async_engine(POSTGRES_URL)
async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False
)
