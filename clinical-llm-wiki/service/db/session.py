"""Synchronous PostgreSQL engine and transaction factory."""

from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker


EXPECTED_DRIVER = "postgresql+psycopg"


def database_url_from_environment() -> str:
    """Load the database URL without supplying an unsafe checked-in fallback."""

    database_url = os.environ.get("KNOWLEDGE_DATABASE_URL")
    if not database_url:
        raise RuntimeError("KNOWLEDGE_DATABASE_URL is required")
    url = make_url(database_url)
    if url.drivername != EXPECTED_DRIVER:
        raise ValueError(f"KNOWLEDGE_DATABASE_URL must use {EXPECTED_DRIVER}")
    return database_url


def create_database_engine(
    database_url: str,
    *,
    echo: bool = False,
) -> Engine:
    """Create an engine without connecting or mutating the database schema."""

    url = make_url(database_url)
    if url.drivername != EXPECTED_DRIVER:
        raise ValueError(f"database URL must use {EXPECTED_DRIVER}")
    return create_engine(url, echo=echo, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return the sole synchronous unit-of-work factory for repositories."""

    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
