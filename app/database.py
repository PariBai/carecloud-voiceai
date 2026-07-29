"""Database engine, session factory, and initialisation.

SQLite is used for the assessment: zero-config, file-backed, and it satisfies
the only hard storage requirement — persistence across restarts. The engine
URL is swappable via DATABASE_URL, so moving to Postgres later is a config
change, not a code change.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Base

# `check_same_thread=False` is required because FastAPI serves requests from a
# threadpool and a connection may be touched by a different thread than the one
# that created it. Sessions are still short-lived and per-request.
_connect_args = (
    {"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    future=True,
)


# Enforce foreign keys / good defaults on every SQLite connection.
if settings.DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
