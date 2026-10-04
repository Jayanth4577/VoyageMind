"""SQLAlchemy engine/session wiring.

Sync SQLAlchemy 2.0 style; PostgreSQL in production (Neon/Render), SQLite
fallback for local tests so the suite runs without external infrastructure.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _normalize_postgres_url(url: str) -> str:
    """Managed-database dashboards (Neon, Render) hand out URLs as
    postgresql://... but this project ships psycopg 3, not psycopg2 — without
    the driver suffix the engine can't load its dialect and deploys crash.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _make_engine(url: str):
    url = _normalize_postgres_url(url)
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})

    connect_args: dict = {}
    if "neon.tech" in url or "pooler" in url:
        # Neon's pgbouncer is transaction-mode: psycopg's server-side prepared
        # statements break Alembic DDL with "_pgbouncer_... already exists".
        connect_args["statement_cache_size"] = 0
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


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
