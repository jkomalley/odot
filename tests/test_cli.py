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

    # Test interactive prompt for add
    interactive = runner.invoke(
        app, ["add", "--priority", "2"], input="Interactive task\n"
    )
    assert interactive.exit_code == 0
    assert "Interactive task" in interactive.stdout


def test_prompt_task_selection(monkeypatch, session):
    """Test the TUI selection prompt internally tracking missing tasks natively."""
    from odot.cli import prompt_task_selection
    import typer

    # Needs to raise evaluating empty branches
    with pytest.raises(typer.Exit):
        prompt_task_selection(session, "action")

    # Mocking choices simulating arrows
    runner.invoke(app, ["add", "Mock selection task"])

    class MockSelect:
        def ask(self):
            return 1

    monkeypatch.setattr("questionary.select", lambda *a, **k: MockSelect())

    assert prompt_task_selection(session, "select") == 1

    # Test cancelled interaction bounds explicitly natively
    class MockSelectCancelled:
        def ask(self):
            return None

    monkeypatch.setattr("questionary.select", lambda *a, **k: MockSelectCancelled())

    with pytest.raises(typer.Exit):
        prompt_task_selection(session, "select")


def test_show_command(monkeypatch):
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

    # Test interactive prompt for show
    monkeypatch.setattr("odot.cli.prompt_task_selection", lambda db, action: 1)
    interactive = runner.invoke(app, ["show"])
    assert interactive.exit_code == 0
    assert "Show me" in interactive.stdout


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


def test_update_command(monkeypatch):
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

    # Test updating nothing (No fields selected via TUI form)
    class MockEmptyCheckbox:
        def ask(self):
            return []

    monkeypatch.setattr("questionary.checkbox", lambda *a, **k: MockEmptyCheckbox())
    empty = runner.invoke(app, ["update", "1"])
    assert empty.exit_code == 1
    assert "No updates provided." in empty.stdout

    # Test completely answering all fields dynamically inside TUI interactive forms
    runner.invoke(app, ["add", "Second task here"])

    class MockFullCheckbox:
        def ask(self):
            return ["content", "priority", "category", "done"]

    class MockSelectPriority:
        def ask(self):
            return "3"

    class MockConfirmDone:
        def ask(self):
            return True

    monkeypatch.setattr("questionary.checkbox", lambda *a, **k: MockFullCheckbox())
    monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *a: "Interactively Updated")
    monkeypatch.setattr("questionary.select", lambda *a, **k: MockSelectPriority())
    monkeypatch.setattr("questionary.confirm", lambda *a, **k: MockConfirmDone())

    tui_all = runner.invoke(app, ["update", "2"])
    assert tui_all.exit_code == 0

    # Check changes evaluated correctly
    verify2 = runner.invoke(app, ["show", "2"])
    assert "Interactively Updated" in verify2.stdout
    assert "3" in verify2.stdout
    assert "Done" in verify2.stdout

    # Test interactive prompt for task ID mapping missing IDs implicitly skipping forms when explicit fields exist natively
    monkeypatch.setattr("odot.cli.prompt_task_selection", lambda db, action: 1)
    interactive = runner.invoke(app, ["update", "--priority", "1"])
    assert interactive.exit_code == 0
    assert "Successfully updated task 1" in interactive.stdout

    # Test missing task natively handled efficiently passing correctly skipping checks dynamically
    missing = runner.invoke(app, ["update", "999", "--done"])
    assert missing.exit_code == 1
    assert "Task 999 not found" in missing.stdout


def test_rm_command(monkeypatch):
    """Test removing a task via CLI."""
    runner.invoke(app, ["add", "Delete me"])
    runner.invoke(app, ["add", "Delete me too"])
    runner.invoke(app, ["add", "Task three"])

    # Test deletion with explicit force flag
    result = runner.invoke(app, ["rm", "1", "--force"])
    assert result.exit_code == 0
    assert "Deleted task 1" in result.stdout

    # Verify deletion
    verify = runner.invoke(app, ["show", "1"])
    assert verify.exit_code == 1

    # Test aborted deletion via confirm
    aborted = runner.invoke(app, ["rm", "2"], input="n\n")
    assert aborted.exit_code == 1
    assert "Are you sure you want to delete task 2?" in aborted.stdout

    # Test confirmed deletion mapping user interactive bounds securely evaluating task_id prompt natively
    monkeypatch.setattr("odot.cli.prompt_task_selection", lambda db, action: 2)
    confirmed = runner.invoke(app, ["rm"], input="y\n")
    assert confirmed.exit_code == 0
    assert "Deleted task 2" in confirmed.stdout

    # Test deleting missing task
    missing = runner.invoke(app, ["rm", "999", "--force"])
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
