"""Pytest fixtures and configuration."""

import pytest
from sqlmodel import Session, SQLModel, create_engine

# Use in-memory SQLite for testing to ensure speed and isolation
sqlite_url = "sqlite:///:memory:"
engine = create_engine(sqlite_url)


@pytest.fixture(name="session")
def session_fixture():
    """Provides a fresh database session for tests."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client_session")
def client_session_fixture(session):
    """Provides a dependency override for the CLI commands."""

    def get_session_override():
        return session

    # We will use this fixture later in test_cli to override main.app dependency
    yield get_session_override
