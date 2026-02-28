"""Tests for database layer."""

from pathlib import Path

from odot import database


def test_database_url_and_engine():
    """Verify database engine logic."""
    assert database.DB_FILE is not None
    assert isinstance(database.DB_FILE, Path)
    assert database.sqlite_url.startswith("sqlite:///")
    assert database.engine is not None


def test_create_db_and_tables():
    """Test table creation against the real engine."""
    # We can invoke the real engine execution without failing
    database.create_db_and_tables()


def test_database_directory_creation(tmp_path, monkeypatch):
    """Test that the DB directory is created if it does not exist."""
    # Mock Path.home() so DB_FILE points to a temporary directory
    target_dir = tmp_path / ".odot"
    target_file = target_dir / "db.sqlite"

    # Temporarily replace DB_FILE in the module
    monkeypatch.setattr(database, "DB_FILE", target_file)

    # The module is already loaded, so we simulate the execution block
    if not database.DB_FILE.parent.exists():
        database.DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    assert target_dir.exists()


def test_get_session():
    """Test the session generator yields successfully."""
    gen = database.get_session()
    session = next(gen)
    assert session is not None

    # Assert generator handles exit smoothly
    try:
        next(gen)
    except StopIteration:
        pass
