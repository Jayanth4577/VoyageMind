"""Test fixtures: isolated SQLite DB per test, no external services required."""

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_voyagemind.db")

import pytest
from fastapi.testclient import TestClient

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
