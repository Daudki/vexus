"""
Database engine + session management.

`get_db` is the FastAPI dependency every router uses to obtain a session.
Routers must never import the engine or session factory directly — this
keeps the persistence layer swappable (SQLite dev -> PostgreSQL prod)
without touching a single route.
"""
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings

settings = get_settings()

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(settings.DATABASE_URL, connect_args=_connect_args, future=True)

if _is_sqlite:
    # SQLite ignores FOREIGN KEY constraints unless a connection
    # explicitly turns them on — unlike Postgres, which always
    # enforces them. Without this, deleting a row that other tables
    # still reference (e.g. a user with audit log history) silently
    # orphans those references in dev/SQLite instead of failing the
    # way it correctly would in production.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped session and finalize its transaction.

    Individual repositories may call `db.commit()` themselves mid-request
    (several modules do), but nothing guaranteed that the *last* unit of
    work in a request — e.g. an audit-log write added after a service
    call already committed — ever got persisted. Without this, every
    write made after the last explicit commit() was silently discarded
    when the session closed at the end of the request (uncommitted
    changes are rolled back on close). Tests never caught this because
    the test fixtures reuse one long-lived session across setup, the
    request, and assertions, so flushed-but-uncommitted data was still
    visible within that same session.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()