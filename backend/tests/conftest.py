"""Test fixtures: isolated SQLite DB per test, no external services required."""

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_voyagemind.db")
# Generous budgets so the suite doesn't trip rate limiting; the dedicated
# rate-limit test lowers them via settings monkeypatch.
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "100000")
os.environ.setdefault("AUTH_RATE_LIMIT_PER_MINUTE", "100000")

import pytest
from fastapi.testclient import TestClient

from app import models  # noqa: F401 - register all ORM models
from app.core.database import Base, engine
from app.main import create_app


@pytest.fixture()
def db_tables():
    """Create/drop the full schema around each test (works with plain SessionLocal too)."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture()
def client(db_tables):
    with TestClient(create_app()) as c:
        yield c
