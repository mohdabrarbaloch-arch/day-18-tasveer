"""Database engine and session management.

SQLAlchemy 2.0 style. SQLite is the default so the project runs with no
external services; point DATABASE_URL at Postgres for production.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base for every ORM model."""


def _engine_kwargs() -> dict:
    if settings.database_url.startswith("sqlite"):
        # check_same_thread=False lets FastAPI's threadpool share the connection.
        return {"connect_args": {"check_same_thread": False}, "pool_pre_ping": True}
    return {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10}


engine = create_engine(settings.database_url, **_engine_kwargs())

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables. Fine for a single deploy; use Alembic once you scale."""
    from app import models  # noqa: F401  (import registers the models)

    Base.metadata.create_all(bind=engine)
