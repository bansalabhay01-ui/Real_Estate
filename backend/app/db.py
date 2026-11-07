"""Database engine and sessions: SQLite while developing, Postgres in production (set DATABASE_URL)."""

from collections.abc import Iterator

import logging

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

_IS_SQLITE = settings.database_url.startswith("sqlite")

engine = create_engine(
    settings.database_url,
    # FastAPI runs sync endpoints in worker threads; wait up to 30 s for a lock instead of failing.
    connect_args={"check_same_thread": False, "timeout": 30} if _IS_SQLITE else {},
    pool_pre_ping=not _IS_SQLITE,
)

if _IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")  # the dashboard can read while events are written
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create any missing tables, and add columns that were added to the models after a table was created."""
    from . import models  # noqa: F401  (importing registers the tables)

    Base.metadata.create_all(engine)
    _add_missing_columns()


def _add_missing_columns() -> None:
    """A tiny migration step: ALTER TABLE ... ADD COLUMN for new nullable columns, plus their indexes.

    Enough while the team only ever adds columns. Switch to Alembic if a column is ever renamed or changed.
    """
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {column["name"] for column in inspector.get_columns(table.name)}
            added = [column for column in table.columns if column.name not in existing]
            for column in added:
                column_type = column.type.compile(dialect=engine.dialect)
                connection.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}'))
                logging.getLogger("leadops.db").info("Added column %s.%s", table.name, column.name)
            names = {column.name for column in added}
            for index in table.indexes:
                if names & {column.name for column in index.columns}:
                    index.create(connection, checkfirst=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one database session per request."""
    with SessionLocal() as db:
        yield db
