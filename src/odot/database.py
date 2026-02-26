"""Database connection and session management."""

from pathlib import Path
from sqlmodel import Session, create_engine

# Example path; will be configured further based on step 2 of outline
DB_FILE = Path.home() / ".odot" / "db.sqlite"

if not DB_FILE.parent.exists():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)

sqlite_url = f"sqlite:///{DB_FILE}"
engine = create_engine(sqlite_url, echo=False)


def create_db_and_tables():
    """Create the database tables."""
    pass  # To be implemented


def get_session():
    """Dependency provider for database sessions."""
    with Session(engine) as session:
        yield session
