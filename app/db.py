"""Database engine and session management.

Uses Neon Postgres when ``DATABASE_URL`` is set; otherwise falls back to a local
SQLite file so the project runs with zero external setup.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

DATABASE_URL = settings.database_url or "sqlite:///./cardekho.db"

# Bare postgresql:// URLs (e.g. from Render/Neon dashboards) default to the
# psycopg2 dialect in SQLAlchemy, but we ship psycopg3 (psycopg[binary]).
# Rewrite the scheme so SQLAlchemy picks the right driver automatically.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# SQLite needs this flag to be usable across FastAPI's threadpool.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
