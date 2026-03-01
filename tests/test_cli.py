"""Integration tests for CLI."""

import pytest
from typer.testing import CliRunner
from odot.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def override_db_dependency(monkeypatch, session):
    """Override the database session for all CLI tests via monkeypatching the context provider."""
    from odot import database

    def mock_get_session():
        yield session

    monkeypatch.setattr(database, "get_session", mock_get_session)


def test_init_db():
    """Test the init-db command."""
    result = runner.invoke(app, ["init-db"])
    assert result.exit_code == 0
    assert "Database initialized successfully" in result.stdout


def test_help():
    """Test the help command."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "A minimalist CLI task manager." in result.stdout


def test_version():
    """Test the version flag."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "odot version:" in result.stdout


def test_add_command():
    """Test adding a task via CLI."""
    result = runner.invoke(
        app, ["add", "Test Task", "--priority", "3", "--category", "work"]
    )
    assert result.exit_code == 0
    assert "Added task" in result.stdout
    assert "Test Task" in result.stdout


def test_show_command():
    """Test showing task details via CLI."""
    # Add a task first
    runner.invoke(app, ["add", "Show me"])

    result = runner.invoke(app, ["show", "1"])
    assert result.exit_code == 0
    assert "Show me" in result.stdout
    assert "Pending" in result.stdout

    # Test missing task
    missing = runner.invoke(app, ["show", "999"])
    assert missing.exit_code == 1
    assert "Task 999 not found" in missing.stdout


def test_list_command():
    """Test listing tasks via CLI."""
    # Add some tasks
    runner.invoke(app, ["add", "Task A"])
    runner.invoke(app, ["add", "Task B"])

    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "Task A" in result.stdout
    assert "Task B" in result.stdout


def test_list_command_empty(session):
    """Test list command when no tasks exist."""
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No tasks found" in result.stdout


def test_update_command():
    """Test updating a task via CLI."""
    runner.invoke(app, ["add", "Old Task"])

    # Update properties
    result = runner.invoke(
        app, ["update", "1", "--content", "New Task", "--done", "--priority", "2"]
    )
    assert result.exit_code == 0
    assert "Successfully updated task 1" in result.stdout

    # Verify update
    verify = runner.invoke(app, ["show", "1"])
    assert "New Task" in verify.stdout
    assert "Done" in verify.stdout

    # Test updating category independently testing branch coverage
    category = runner.invoke(app, ["update", "1", "--category", "work"])
    assert category.exit_code == 0
    assert "Successfully updated task 1" in category.stdout

    # Test updating nothing
    empty = runner.invoke(app, ["update", "1"])
    assert empty.exit_code == 1
    assert "No updates provided." in empty.stdout

    # Test missing task
    missing = runner.invoke(app, ["update", "999", "--done"])
    assert missing.exit_code == 1
    assert "Task 999 not found" in missing.stdout


def test_rm_command():
    """Test removing a task via CLI."""
    runner.invoke(app, ["add", "Delete me"])

    result = runner.invoke(app, ["rm", "1"])
    assert result.exit_code == 0
    assert "Deleted task 1" in result.stdout

    # Verify deletion
    verify = runner.invoke(app, ["show", "1"])
    assert verify.exit_code == 1

    # Test deleting missing task
    missing = runner.invoke(app, ["rm", "999"])
    assert missing.exit_code == 1
    assert "Task 999 not found" in missing.stdout


def test_main_execution(monkeypatch):
    """Test the main entrypoint function directly."""
    called = False

    def mock_app():
        nonlocal called
        called = True

    monkeypatch.setattr("odot.cli.app", mock_app)

    from odot.cli import main

    main()
    assert called


def test_module_execution():
    """Test that python -m odot.cli works without errors."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "odot.cli", "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "A minimalist CLI task manager." in result.stdout
