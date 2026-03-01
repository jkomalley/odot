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
    import importlib

    # Mock Path.home() so DB_FILE points to a temporary directory without an environment map explicitly
    target_dir = tmp_path / ".odot"

    monkeypatch.delenv("ODOT_DB_PATH", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    # Force a module reload so it executes the top level conditionals again
    importlib.reload(database)

    assert target_dir.exists()
    assert database.DB_FILE.parent == target_dir


def test_database_directory_env_override(tmp_path, monkeypatch):
    """Test reading the ODOT_DB_PATH env var successfully parsing."""
    import importlib

    # Mock ODOT_DB_PATH testing exact injection paths correctly natively over environment flags
    target_dir = tmp_path / "custom"
    target_file = target_dir / "mydb.sqlite"

    monkeypatch.setenv("ODOT_DB_PATH", str(target_file))

    # Force a module reload so it executes the top level conditionals again
    importlib.reload(database)

    assert target_dir.exists()
    assert database.DB_FILE == target_file


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
