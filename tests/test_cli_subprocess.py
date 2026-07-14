"""Subprocess-level smoke tests: confirm odot works as an installed CLI."""

from __future__ import annotations

import os
import subprocess
import sys


def run_odot(*args, db_path):
    """Invoke `python -m odot` as a real subprocess isolated to db_path."""
    env = {**os.environ, "ODOT_DB_PATH": str(db_path)}
    return subprocess.run(
        [sys.executable, "-m", "odot", *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_version_flag_reports_version(tmp_path):
    result = run_odot("--version", db_path=tmp_path / "db.sqlite")

    assert result.returncode == 0
    assert "odot version:" in result.stdout


def test_help_flag_shows_usage(tmp_path):
    result = run_odot("--help", db_path=tmp_path / "db.sqlite")

    assert result.returncode == 0
    assert "A minimalist CLI task manager." in result.stdout


def test_add_then_list_round_trip(tmp_path):
    db_path = tmp_path / "db.sqlite"

    add_result = run_odot("add", "Buy milk", db_path=db_path)
    assert add_result.returncode == 0
    assert "Added task" in add_result.stdout

    list_result = run_odot("list", db_path=db_path)
    assert list_result.returncode == 0
    assert "Buy milk" in list_result.stdout


def test_invalid_command_exits_nonzero(tmp_path):
    result = run_odot("not-a-real-command", db_path=tmp_path / "db.sqlite")

    assert result.returncode != 0
