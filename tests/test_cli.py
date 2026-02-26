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
