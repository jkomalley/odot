"""Unit tests for core logic."""

from odot import core, database, models


def test_core_stub():
    """Stub test."""
    assert core is not None


def test_database():
    """Test database setup."""
    assert database.DB_FILE is not None
    assert database.sqlite_url is not None
    database.create_db_and_tables()
    session_gen = database.get_session()
    assert session_gen is not None
    try:
        next(session_gen)
    except Exception:
        pass


def test_models():
    """Test models setup."""
    task = models.Task(content="Test")
    assert task.content == "Test"
