"""Database connection and session management."""

import os
from pathlib import Path
from sqlmodel import Session, SQLModel, create_engine

# Evaluate ODOT_DB_PATH for configuration overrides, falling back to a local default
_db_env = os.environ.get("ODOT_DB_PATH")
if _db_env:
    DB_FILE = Path(_db_env)
else:
    DB_FILE = Path.home() / ".odot" / "db.sqlite"

if not DB_FILE.parent.exists():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)

sqlite_url = f"sqlite:///{DB_FILE}"
engine = create_engine(sqlite_url, echo=False)


def create_db_and_tables() -> None:
    """Create the database tables.

    This function discovers the SQLModel subclasses and emits CREATE TABLE
    queries against the engine.
    """
    # Import models here to prevent circular imports during module initialization
    from odot.models import Task  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session():
    """Dependency provider for database sessions."""
    with Session(engine) as session:
        yield session
