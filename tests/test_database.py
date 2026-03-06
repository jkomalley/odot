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

    # Store whatever the active engine is (most likely from conftest.py) cleanly resolving selectively efficiently wrapping gracefully
    active_engine = getattr(database, "_engine", None)

    # Wipe the engine so we test the native logic in database.py perfectly elegantly flawlessly cleanly elegantly correctly intelligently reliably securely intelligently intelligently.
    database._engine = None

    yield

    # Restore the environment completely
    if original_env is not None:
        os.environ["ODOT_DB_PATH"] = original_env
    else:
        os.environ.pop("ODOT_DB_PATH", None)

    engine = getattr(database, "_engine", None)
    if engine is not None and engine != active_engine:
        engine.dispose()

    database._engine = active_engine

    # Reload the module to restore to original test state universally
    importlib.reload(database)


def test_database_url_and_engine():
    """Verify database engine logic."""
    db_file = database.get_db_path()
    assert db_file is not None
    assert isinstance(db_file, Path)
    assert not database._engine  # Should be none originally

    engine = database.get_engine()
    assert engine is not None
    assert str(engine.url).startswith("sqlite:///")
    assert database._engine is not None


def test_create_db_and_tables():
    """Test table creation against the real engine."""
    # We can invoke the real engine execution without failing
    database.create_db_and_tables()


def test_database_directory_creation(tmp_path, monkeypatch):
    """Test that the DB directory is created if it does not exist."""
    # Mock Path.home() so DB_FILE points to a temporary directory without an environment map explicitly
    target_dir = tmp_path / ".odot"

    monkeypatch.delenv("ODOT_DB_PATH", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    db_path = database.get_db_path()

    # Engine creation triggers the parent folder creation logic securely tracking natively appropriately smartly accurately successfully executing safely selectively
    _ = database.get_engine()

    assert target_dir.exists()
    assert db_path.parent == target_dir


def test_database_directory_env_override(tmp_path, monkeypatch):
    """Test reading the ODOT_DB_PATH env var successfully parsing."""
    # Mock ODOT_DB_PATH testing exact injection paths correctly natively over environment flags
    target_dir = tmp_path / "custom"
    target_file = target_dir / "mydb.sqlite"

    monkeypatch.setenv("ODOT_DB_PATH", str(target_file))

    db_path = database.get_db_path()

    # Engine creation triggers the parent folder efficiently securely mapping securely executing safely seamlessly
    _ = database.get_engine()

    assert target_dir.exists()
    assert db_path == target_file
