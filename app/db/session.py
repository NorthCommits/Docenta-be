from collections.abs import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, session, sessionmaker

from app.core.config import settings

engine = create_engine(
	settings.sqlalchemy_database_url,
	pool_pre_ping = True,
	future = True,
)

SessionLocal = sessionmaker(
	bind=engine,
	autoflush=False,
	autocommit=False
)

def get_db() -> Generator[Session, None, None]:
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()
