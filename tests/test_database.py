"""Tests for database layer."""

import os
import pytest
from pathlib import Path

from odot import database


@pytest.fixture(autouse=True)
def restore_database_module():
    """Ensure database.py is cleanly reloaded and independent for each test."""
    import importlib

    # Store the original environment state
    original_env = os.environ.get("ODOT_DB_PATH")

    yield

    # Restore the environment completely
    if original_env is not None:
        os.environ["ODOT_DB_PATH"] = original_env
    else:
        os.environ.pop("ODOT_DB_PATH", None)

    # Dispose of whatever engine was left mapped
    if getattr(database, "engine", None):
        database.engine.dispose()

    # Reload the module to restore to original test state universally
    importlib.reload(database)

    # Dispose the reloaded engine so it doesn't leak either!
    # (Other tests use the mocked `session` fixture, so we don't need this global engine open)
    if getattr(database, "engine", None):
        database.engine.dispose()


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
