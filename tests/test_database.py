"""Tests for database layer."""

import os
from pathlib import Path

import pytest
from sqlmodel import create_engine

from odot import database


@pytest.fixture(autouse=True)
def isolate_engine():
    """Ensure each test starts with no engine configured and restores env vars."""
    original_env = os.environ.get("ODOT_DB_PATH")

    database.reset_engine()

    yield

    if original_env is not None:
        os.environ["ODOT_DB_PATH"] = original_env
    else:
        os.environ.pop("ODOT_DB_PATH", None)

    database.reset_engine()


def test_database_url_and_engine():
    """Verify database engine logic."""
    db_file = database.get_db_path()
    assert db_file is not None
    assert isinstance(db_file, Path)

    engine = database.get_engine()
    assert engine is not None
    assert str(engine.url).startswith("sqlite:///")
    engine.dispose()


def test_create_db_and_tables():
    """Test table creation against the real engine."""
    # We can invoke the real engine execution without failing
    database.create_db_and_tables()
    database.get_engine().dispose()


def test_database_directory_creation(tmp_path, monkeypatch):
    """Test that the DB directory is created if it does not exist."""
    target_dir = tmp_path / ".odot"

    monkeypatch.delenv("ODOT_DB_PATH", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    db_path = database.get_db_path()

    engine = database.get_engine()

    assert target_dir.exists()
    assert db_path.parent == target_dir
    engine.dispose()


def test_database_directory_env_override(tmp_path, monkeypatch):
    """Test reading the ODOT_DB_PATH env var successfully parsing."""
    target_dir = tmp_path / "custom"
    target_file = target_dir / "mydb.sqlite"

    monkeypatch.setenv("ODOT_DB_PATH", str(target_file))

    db_path = database.get_db_path()

    engine = database.get_engine()

    assert target_dir.exists()
    assert db_path == target_file
    engine.dispose()


def test_set_engine_overrides_singleton():
    """Test that set_engine installs a specific engine as the singleton."""
    custom_engine = create_engine("sqlite:///:memory:")

    database.set_engine(custom_engine)

    assert database.get_engine() is custom_engine

    custom_engine.dispose()


def test_reset_engine_clears_singleton():
    """Test that reset_engine forces get_engine to create a fresh engine."""
    first_engine = database.get_engine()

    database.reset_engine()

    second_engine = database.get_engine()

    assert first_engine is not second_engine

    first_engine.dispose()
    second_engine.dispose()
