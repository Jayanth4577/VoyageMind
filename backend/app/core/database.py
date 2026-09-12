"""SQLAlchemy engine/session wiring.

Sync SQLAlchemy 2.0 style; PostgreSQL in production, SQLite fallback for
local tests so the suite runs without external infrastructure.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True)


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Alembic owns migrations in production; this keeps dev/test/bootstrap simple.
    from app import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=engine)
