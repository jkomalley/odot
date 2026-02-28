"""Integration tests for CLI."""

from typer.testing import CliRunner
from odot.main import app

runner = CliRunner()


def test_init_db():
    """Test the init-db command."""
    result = runner.invoke(app, ["init-db"])
    assert result.exit_code == 0
    assert "Initializing database..." in result.stdout


def test_help():
    """Test the help command."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "A minimalist CLI task manager." in result.stdout


def test_add_command():
    result = runner.invoke(app, ["add", "Test Task"])
    assert result.exit_code == 0


def test_show_command():
    result = runner.invoke(app, ["show", "1"])
    assert result.exit_code == 0


def test_list_command():
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0


def test_update_command():
    result = runner.invoke(app, ["update", "1"])
    assert result.exit_code == 0


def test_rm_command():
    result = runner.invoke(app, ["rm", "1"])
    assert result.exit_code == 0


def test_main_execution(monkeypatch):
    """Test the main entrypoint function directly."""
    # Mock app() call to prevent actual execution blocking
    called = False

    def mock_app():
        nonlocal called
        called = True

    monkeypatch.setattr("odot.main.app", mock_app)

    from odot.main import main

    main()
    assert called


def test_module_execution():
    """Test that python -m odot.main works without errors."""
    import subprocess
    import sys

    # Run the module in a subprocess and ask for help to exit cleanly
    result = subprocess.run(
        [sys.executable, "-m", "odot.main", "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "A minimalist CLI task manager." in result.stdout
