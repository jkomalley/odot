"""Pytest fixtures and configuration."""

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# Use in-memory SQLite for testing to ensure speed and isolation
sqlite_url = "sqlite:///:memory:"


@pytest.fixture(name="engine", scope="session")
def engine_fixture():
    """Provides a global StaticPool engine securely preventing ResourceWarnings."""
    engine = create_engine(
        sqlite_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def cleanup_global_engine():
    """Ensure the global application database engine is disposed properly after tests."""
    yield
    from odot import database

    if getattr(database, "engine", None):
        database.engine.dispose()


@pytest.fixture(name="session")
def session_fixture(engine):
    """Provides a fresh database session for tests."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client_session")
def client_session_fixture(session):
    """Provides a dependency override for the CLI commands."""

    def get_session_override():
        yield session

    # We will use this fixture later in test_cli to override main.app dependency
    yield get_session_override
