"""Database connection and session management."""

import os
from pathlib import Path
from sqlmodel import SQLModel, create_engine
from sqlalchemy.engine import Engine

_engine: Engine | None = None


def get_db_path() -> Path:
    """Return the path to the SQLite database file.

    Returns:
        Path to the database file.
    """
    db_env = os.environ.get("ODOT_DB_PATH")
    if db_env:
        return Path(db_env)
    return Path.home() / ".odot" / "db.sqlite"


def get_engine() -> Engine:
    """Return the singleton database engine, creating it on first call.

    Returns:
        The SQLAlchemy engine instance.
    """
    global _engine
    if _engine is None:
        db_file = get_db_path()
        if not db_file.parent.exists():
            db_file.parent.mkdir(parents=True, exist_ok=True)

        sqlite_url = f"sqlite:///{db_file}"
        _engine = create_engine(sqlite_url, echo=False)

    return _engine


def create_db_and_tables() -> None:
    """Create the database tables.

    This function discovers the SQLModel subclasses and emits CREATE TABLE
    queries against the engine.
    """
    # Import models here to prevent circular imports during module initialization
    from odot.models import Task  # noqa: F401

    SQLModel.metadata.create_all(get_engine())
