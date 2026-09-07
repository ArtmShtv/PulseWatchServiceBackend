from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_sync_db_url

sync_engine = create_engine(get_sync_db_url())
CelerySession = sessionmaker(bind=sync_engine)