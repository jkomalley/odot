"""Integration tests for CLI."""

import json

import pytest
from typer.testing import CliRunner

from odot.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def override_db_dependency(monkeypatch, session, tmp_path):
    """Override the database session for all CLI tests via monkeypatching Session."""

    def mock_session(*args, **kwargs):
        return session

    monkeypatch.setattr("odot.cli.Session", mock_session)

    # Provide a pre-existing db path so auto-init doesn't trigger in unrelated tests
    fake_db = tmp_path / "db.sqlite"
    fake_db.touch()
    monkeypatch.setattr("odot.database.get_db_path", lambda: fake_db)


def test_init_db():
    """Test the init-db command."""
    result = runner.invoke(app, ["init-db"])
    assert result.exit_code == 0
    assert "Database initialized successfully" in result.stdout


def test_main_callback_skips_init_when_session_present():
    """When ctx.obj already holds a session, the callback leaves it untouched."""
    from odot.cli import main_callback

    class FakeContext:
        obj = "existing-session"

    ctx = FakeContext()
    main_callback(ctx)  # ty: ignore[invalid-argument-type]
    assert ctx.obj == "existing-session"


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
    """Test adding a task via CLI with explicit content."""
    result = runner.invoke(
        app, ["add", "Test Task", "--priority", "3", "--category", "work"]
    )
    assert result.exit_code == 0
    assert "Added task" in result.stdout
    assert "Test Task" in result.stdout


def test_add_command_interactive_prompt():
    """When content is omitted, add falls back to an interactive prompt."""
    result = runner.invoke(app, ["add", "--priority", "2"], input="Interactive task\n")
    assert result.exit_code == 0
    assert "Interactive task" in result.stdout


def test_prompt_task_selection_raises_when_no_tasks(session):
    """Selecting a task with an empty task list exits instead of prompting."""
    import typer

    from odot.cli import prompt_task_selection

    with pytest.raises(typer.Exit):
        prompt_task_selection(session, "action")


def test_prompt_task_selection_returns_chosen_id(monkeypatch, session):
    """Selecting a task returns the id chosen via the TUI list."""
    from odot.cli import prompt_task_selection

    runner.invoke(app, ["add", "Mock selection task"])

    class MockSelect:
        def ask(self):
            return 1

    monkeypatch.setattr("questionary.select", lambda *a, **k: MockSelect())

    assert prompt_task_selection(session, "select") == 1


def test_prompt_task_selection_raises_on_cancel(monkeypatch, session):
    """Cancelling the TUI selection (ask returns None) exits."""
    import typer

    from odot.cli import prompt_task_selection

    runner.invoke(app, ["add", "Mock selection task"])

    class MockSelectCancelled:
        def ask(self):
            return None

    monkeypatch.setattr("questionary.select", lambda *a, **k: MockSelectCancelled())

    with pytest.raises(typer.Exit):
        prompt_task_selection(session, "select")


def test_show_command():
    """Test showing task details via CLI."""
    runner.invoke(app, ["add", "Show me"])

    result = runner.invoke(app, ["show", "1"])
    assert result.exit_code == 0
    assert "Show me" in result.stdout
    assert "Pending" in result.stdout
    assert "Updated At" not in result.stdout


def test_show_command_after_update_includes_updated_at():
    """Once a task has been updated, show displays its Updated At field."""
    runner.invoke(app, ["add", "Show me"])
    runner.invoke(app, ["update", "1", "-p", "3"])

    result = runner.invoke(app, ["show", "1"])
    assert result.exit_code == 0
    assert "Updated At" in result.stdout


def test_show_command_missing_task():
    """Showing a nonexistent task reports not-found."""
    result = runner.invoke(app, ["show", "999"])
    assert result.exit_code == 1
    assert "Task 999 not found" in result.stdout


def test_show_command_interactive_prompt(monkeypatch):
    """Omitting a task id falls back to the interactive selection prompt."""
    runner.invoke(app, ["add", "Show me"])
    monkeypatch.setattr("odot.cli.prompt_task_selection", lambda db, action: 1)

    result = runner.invoke(app, ["show"])
    assert result.exit_code == 0
    assert "Show me" in result.stdout


def test_list_command():
    """Test listing tasks via CLI."""
    runner.invoke(app, ["add", "Task A", "--category", "work"])
    runner.invoke(app, ["add", "Task B", "--category", "personal"])
    runner.invoke(app, ["add", "Task C", "--category", "work"])

    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "Task A" in result.stdout
    assert "Task B" in result.stdout
    assert "Task C" in result.stdout


def test_list_command_category_filter():
    """The --category filter restricts listed tasks to one category."""
    runner.invoke(app, ["add", "Task A", "--category", "work"])
    runner.invoke(app, ["add", "Task B", "--category", "personal"])
    runner.invoke(app, ["add", "Task C", "--category", "work"])

    result = runner.invoke(app, ["list", "--category", "work"])
    assert result.exit_code == 0
    assert "Task A" in result.stdout
    assert "Task B" not in result.stdout
    assert "Task C" in result.stdout


def test_list_command_combined_filters():
    """Category and done filters can be combined."""
    runner.invoke(app, ["add", "Task A", "--category", "work"])
    runner.invoke(app, ["add", "Task B", "--category", "personal"])
    runner.invoke(app, ["add", "Task C", "--category", "work"])
    runner.invoke(app, ["update", "2", "--done"])

    result = runner.invoke(app, ["list", "-c", "personal", "--done"])
    assert result.exit_code == 0
    assert "Task B" in result.stdout
    assert "Task A" not in result.stdout


def test_list_command_sort_order():
    """The --sort flag orders tasks ascending, and --reverse flips it."""
    runner.invoke(app, ["add", "Task A", "--category", "work"])
    runner.invoke(app, ["add", "Task B", "--category", "personal"])
    runner.invoke(app, ["add", "Task C", "--category", "work"])
    runner.invoke(app, ["update", "1", "-p", "3"])
    runner.invoke(app, ["update", "3", "-p", "2"])

    sort_asc = runner.invoke(app, ["list", "--sort", "priority"])
    assert sort_asc.exit_code == 0
    assert sort_asc.stdout.index("Task B") < sort_asc.stdout.index("Task C")
    assert sort_asc.stdout.index("Task C") < sort_asc.stdout.index("Task A")

    sort_desc = runner.invoke(app, ["list", "--sort", "priority", "--reverse"])
    assert sort_desc.exit_code == 0
    assert sort_desc.stdout.index("Task A") < sort_desc.stdout.index("Task C")
    assert sort_desc.stdout.index("Task C") < sort_desc.stdout.index("Task B")


def test_list_command_invalid_sort_field():
    """An unrecognized --sort field is rejected."""
    runner.invoke(app, ["add", "Task A"])

    result = runner.invoke(app, ["list", "--sort", "invalid_field"])
    assert result.exit_code == 1
    assert "Invalid sort field" in result.stdout


def test_list_command_empty(session):
    """Test list command when no tasks exist."""
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No tasks found" in result.stdout


def test_search_command_matches_phrase():
    """Search returns only tasks whose content matches the given phrase."""
    runner.invoke(app, ["add", "Unique search phrase"])
    runner.invoke(app, ["add", "Another different task"])

    result = runner.invoke(app, ["search", "search phrase"])
    assert result.exit_code == 0
    assert "Unique search phrase" in result.stdout
    assert "different task" not in result.stdout


def test_search_command_no_matches():
    """Search reports when no tasks match the phrase."""
    runner.invoke(app, ["add", "Unique search phrase"])

    result = runner.invoke(app, ["search", "nonexistent"])
    assert result.exit_code == 0
    assert "No tasks matching 'nonexistent' found." in result.stdout


def test_update_command_sets_explicit_fields():
    """Explicit --content/--done/--priority flags update those fields."""
    runner.invoke(app, ["add", "Old Task"])

    result = runner.invoke(
        app, ["update", "1", "--content", "New Task", "--done", "--priority", "2"]
    )
    assert result.exit_code == 0
    assert "Successfully updated task 1" in result.stdout

    verify = runner.invoke(app, ["show", "1"])
    assert "New Task" in verify.stdout
    assert "Done" in verify.stdout


def test_update_command_single_field():
    """A single --category flag updates only that field."""
    runner.invoke(app, ["add", "Old Task"])

    result = runner.invoke(app, ["update", "1", "--category", "work"])
    assert result.exit_code == 0
    assert "Successfully updated task 1" in result.stdout


def test_update_command_no_fields_selected(monkeypatch):
    """Cancelling the interactive checkbox with no fields selected is an error."""
    runner.invoke(app, ["add", "Old Task"])

    class MockEmptyCheckbox:
        def ask(self):
            return []

    monkeypatch.setattr("questionary.checkbox", lambda *a, **k: MockEmptyCheckbox())

    result = runner.invoke(app, ["update", "1"])
    assert result.exit_code == 1
    assert "No updates provided." in result.stdout


def test_update_command_interactive_all_fields(monkeypatch):
    """Selecting every field in the interactive TUI updates them all."""
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

    result = runner.invoke(app, ["update", "1"])
    assert result.exit_code == 0

    verify = runner.invoke(app, ["show", "1"])
    assert "Interactively Updated" in verify.stdout
    assert "3" in verify.stdout
    assert "Done" in verify.stdout


def test_update_command_explicit_fields_skip_task_prompt(monkeypatch):
    """With explicit update flags given, no task-selection prompt should appear."""
    runner.invoke(app, ["add", "Old Task"])
    monkeypatch.setattr("odot.cli.prompt_task_selection", lambda db, action: 1)

    result = runner.invoke(app, ["update", "--priority", "1"])
    assert result.exit_code == 0
    assert "Successfully updated task 1" in result.stdout


def test_update_command_missing_task():
    """Updating a nonexistent task should report not-found."""
    result = runner.invoke(app, ["update", "999", "--done"])
    assert result.exit_code == 1
    assert "Task 999 not found" in result.stdout


def test_update_interactive_partial_content_only(monkeypatch):
    """Selecting only 'content' in the TUI checkbox skips the other fields."""
    runner.invoke(app, ["add", "Partial task"])

    class MockContentOnlyCheckbox:
        def ask(self):
            return ["content"]

    monkeypatch.setattr(
        "questionary.checkbox", lambda *a, **k: MockContentOnlyCheckbox()
    )
    monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *a: "Only content changed")

    result = runner.invoke(app, ["update", "1"])
    assert result.exit_code == 0
    assert "Successfully updated task 1" in result.stdout


def test_update_interactive_partial_cancelled_priority(monkeypatch):
    """Selecting 'priority' but cancelling its prompt leaves the field unset."""
    runner.invoke(app, ["add", "Partial task"])

    class MockPriorityOnlyCheckbox:
        def ask(self):
            return ["priority"]

    class MockSelectCancelled:
        def ask(self):
            return None

    monkeypatch.setattr(
        "questionary.checkbox", lambda *a, **k: MockPriorityOnlyCheckbox()
    )
    monkeypatch.setattr("questionary.select", lambda *a, **k: MockSelectCancelled())

    result = runner.invoke(app, ["update", "1"])
    assert result.exit_code == 0
    assert "Successfully updated task 1" in result.stdout


def test_done_command():
    """Marking a task done via the done shortcut updates its status."""
    runner.invoke(app, ["add", "Finish me"])

    result = runner.invoke(app, ["done", "1"])
    assert result.exit_code == 0
    assert "marked as done" in result.stdout

    verify = runner.invoke(app, ["show", "1"])
    assert "Done" in verify.stdout


def test_done_command_missing_task():
    """Marking a nonexistent task done reports not-found."""
    result = runner.invoke(app, ["done", "999"])
    assert result.exit_code == 1
    assert "Task 999 not found" in result.stdout


def test_done_command_interactive_prompt(monkeypatch):
    """Omitting a task id falls back to the interactive selection prompt."""
    runner.invoke(app, ["add", "Finish me"])
    monkeypatch.setattr("odot.cli.prompt_task_selection", lambda db, action: 1)

    result = runner.invoke(app, ["done"])
    assert result.exit_code == 0
    assert "marked as done" in result.stdout


def test_undo_command():
    """Re-opening a completed task via undo resets its status."""
    runner.invoke(app, ["add", "Already done"])
    runner.invoke(app, ["done", "1"])

    result = runner.invoke(app, ["undo", "1"])
    assert result.exit_code == 0
    assert "re-opened" in result.stdout

    verify = runner.invoke(app, ["show", "1"])
    assert "Pending" in verify.stdout


def test_undo_command_missing_task():
    """Undoing a nonexistent task reports not-found."""
    result = runner.invoke(app, ["undo", "999"])
    assert result.exit_code == 1
    assert "Task 999 not found" in result.stdout


def test_undo_command_interactive_prompt(monkeypatch):
    """Omitting a task id falls back to the interactive selection prompt."""
    runner.invoke(app, ["add", "Already done"])
    runner.invoke(app, ["done", "1"])
    monkeypatch.setattr("odot.cli.prompt_task_selection", lambda db, action: 1)

    result = runner.invoke(app, ["undo"])
    assert result.exit_code == 0
    assert "re-opened" in result.stdout


def test_rm_command_with_force_flag():
    """The --force flag deletes a task without a confirmation prompt."""
    runner.invoke(app, ["add", "Delete me"])

    result = runner.invoke(app, ["rm", "1", "--force"])
    assert result.exit_code == 0
    assert "Deleted task 1" in result.stdout

    verify = runner.invoke(app, ["show", "1"])
    assert verify.exit_code == 1


def test_rm_command_aborted_confirmation():
    """Declining the confirmation prompt leaves the task in place."""
    runner.invoke(app, ["add", "Delete me too"])

    result = runner.invoke(app, ["rm", "1"], input="n\n")
    assert result.exit_code == 1
    assert "Are you sure you want to delete task 1?" in result.stdout


def test_rm_command_interactive_prompt_confirmed(monkeypatch):
    """Confirmed deletion via the interactive task-id prompt removes the task."""
    runner.invoke(app, ["add", "Delete me too"])
    monkeypatch.setattr("odot.cli.prompt_task_selection", lambda db, action: 1)

    result = runner.invoke(app, ["rm"], input="y\n")
    assert result.exit_code == 0
    assert "Deleted task 1" in result.stdout


def test_rm_command_missing_task():
    """Deleting a nonexistent task reports not-found."""
    result = runner.invoke(app, ["rm", "999", "--force"])
    assert result.exit_code == 1
    assert "Task 999 not found" in result.stdout


def test_clean_command_aborted():
    """Declining the clean confirmation prompt leaves completed tasks in place."""
    runner.invoke(app, ["add", "Keep me 1"])
    runner.invoke(app, ["add", "Delete me 1"])
    runner.invoke(app, ["update", "2", "--done"])

    result = runner.invoke(app, ["clean"], input="n\n")
    assert result.exit_code == 1
    assert "Are you sure you want to delete all completed tasks?" in result.stdout


def test_clean_command_confirmed():
    """Confirming clean removes only the completed tasks."""
    runner.invoke(app, ["add", "Keep me 1"])
    runner.invoke(app, ["add", "Delete me 1"])
    runner.invoke(app, ["add", "Keep me 2"])
    runner.invoke(app, ["add", "Delete me 2"])
    runner.invoke(app, ["update", "2", "--done"])
    runner.invoke(app, ["update", "4", "--done"])

    result = runner.invoke(app, ["clean"], input="y\n")
    assert result.exit_code == 0
    assert "Deleted 2 completed tasks." in result.stdout

    list_after = runner.invoke(app, ["list"])
    assert "Keep me 1" in list_after.stdout
    assert "Keep me 2" in list_after.stdout
    assert "Delete me 1" not in list_after.stdout


def test_clean_command_nothing_to_clean():
    """Cleaning with no completed tasks reports there is nothing to delete."""
    runner.invoke(app, ["add", "Keep me 1"])

    result = runner.invoke(app, ["clean", "--force"])
    assert result.exit_code == 0
    assert "No completed tasks to delete." in result.stdout


def test_purge_command_aborted():
    """Declining the purge confirmation prompt leaves all tasks in place."""
    runner.invoke(app, ["add", "Delete me 1"])

    result = runner.invoke(app, ["purge"], input="n\n")
    assert result.exit_code == 1
    assert "WARNING: This will permanently delete ALL tasks." in result.stdout

    list_after = runner.invoke(app, ["list"])
    assert "Delete me 1" in list_after.stdout


def test_purge_command_confirmed():
    """Confirming purge deletes every task in the database."""
    runner.invoke(app, ["add", "Delete me 1"])
    runner.invoke(app, ["add", "Delete me 2"])

    result = runner.invoke(app, ["purge"], input="y\n")
    assert result.exit_code == 0
    assert "Purged 2 tasks" in result.stdout


def test_purge_command_force_with_no_tasks():
    """Purging an empty database with --force reports zero tasks purged."""
    result = runner.invoke(app, ["purge", "--force"])
    assert result.exit_code == 0
    assert "Purged 0 tasks" in result.stdout


def test_export_command_writes_filtered_file(tmp_path):
    """Exporting with a category filter and --pretty writes only matching tasks."""
    runner.invoke(app, ["add", "Export task 1", "--category", "work"])
    runner.invoke(app, ["add", "Export task 2"])

    export_file = tmp_path / "export.json"
    result = runner.invoke(
        app, ["export", str(export_file), "--category", "work", "--pretty"]
    )
    assert result.exit_code == 0
    assert "Successfully exported 1 tasks" in result.stdout

    with export_file.open() as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]["content"] == "Export task 1"


def test_export_command_without_path_writes_to_stdout():
    """Exporting without a target path prints JSON to stdout, no file written."""
    runner.invoke(app, ["add", "Export task 1", "--category", "work"])

    result = runner.invoke(app, ["export", "--category", "work"])
    assert result.exit_code == 0
    assert "Export task 1" in result.stdout
    assert "Successfully exported" not in result.stdout


def test_export_command_pretty_to_stdout():
    """The --pretty flag also applies to stdout export output."""
    runner.invoke(app, ["add", "Export task 1", "--category", "work"])

    result = runner.invoke(app, ["export", "--pretty"])
    assert result.exit_code == 0
    assert "Export task 1" in result.stdout


def test_import_command_adds_tasks(tmp_path):
    """Importing a JSON file adds its tasks alongside existing ones."""
    import_file = tmp_path / "import.json"
    payload = [
        {
            "content": "CLI Import Task",
            "priority": 3,
            "category": "imported",
            "is_done": False,
        }
    ]
    with import_file.open("w") as f:
        json.dump(payload, f)
    runner.invoke(app, ["add", "Pre existing task"])

    result = runner.invoke(app, ["import", str(import_file)])
    assert result.exit_code == 0
    assert "Successfully imported 1 tasks" in result.stdout


def test_import_command_clear_aborted(tmp_path):
    """Declining the --clear confirmation leaves the database untouched."""
    import_file = tmp_path / "import.json"
    payload = [{"content": "CLI Import Task", "priority": 3, "is_done": False}]
    with import_file.open("w") as f:
        json.dump(payload, f)
    runner.invoke(app, ["add", "Pre existing task"])

    result = runner.invoke(app, ["import", str(import_file), "--clear"], input="n\n")
    assert result.exit_code == 1
    assert "Are you incredibly sure you want to clear the database?" in result.stdout


def test_import_command_clear_confirmed(tmp_path):
    """Confirming --clear wipes existing tasks before importing the new ones."""
    import_file = tmp_path / "import.json"
    payload = [{"content": "CLI Import Task", "priority": 3, "is_done": False}]
    with import_file.open("w") as f:
        json.dump(payload, f)
    runner.invoke(app, ["add", "Pre existing task"])

    result = runner.invoke(app, ["import", str(import_file), "--clear"], input="y\n")
    assert result.exit_code == 0
    assert "Successfully imported 1 tasks" in result.stdout

    lists = runner.invoke(app, ["list"])
    assert "CLI Import Task" in lists.stdout
    assert "Pre existing task" not in lists.stdout


def test_import_command_missing_file():
    """Importing a missing file exits with typer's standard file-not-found code."""
    result = runner.invoke(app, ["import", "missing.json"])
    assert result.exit_code == 2


def test_import_command_malformed_json(tmp_path):
    """Malformed JSON should be reported as an import failure."""
    bad_json_file = tmp_path / "bad.json"
    bad_json_file.write_text("invalid json")

    result = runner.invoke(app, ["import", str(bad_json_file)])
    assert result.exit_code == 1
    assert "Failed to import tasks" in result.stdout


@pytest.fixture
def seeded_report_tasks():
    """Seed a work task and a completed personal task for report tests."""
    runner.invoke(app, ["add", "Work task", "-c", "work", "-p", "3"])
    runner.invoke(app, ["add", "Personal task", "-c", "personal", "-p", "1"])
    runner.invoke(app, ["update", "2", "--done"])


def test_report_command_markdown(seeded_report_tasks, tmp_path):
    """Generating a Markdown report groups tasks by category with checkboxes."""
    md_file = tmp_path / "report.md"

    result = runner.invoke(app, ["report", str(md_file)])
    assert result.exit_code == 0
    assert "Successfully generated report" in result.stdout
    assert md_file.exists()

    md_content = md_file.read_text()
    assert "# Odot Task Report" in md_content
    assert "## Work" in md_content
    assert "- [ ] Work task (Priority: 3)" in md_content
    assert "## Personal" in md_content
    assert "- [x] Personal task (Priority: 1)" in md_content


def test_report_command_html(seeded_report_tasks, tmp_path):
    """Generating an HTML report with --done filters to completed tasks only."""
    html_file = tmp_path / "report.html"

    result = runner.invoke(app, ["report", str(html_file), "--done"])
    assert result.exit_code == 0
    assert html_file.exists()

    html_content = html_file.read_text()
    assert "<title>Odot Task Report</title>" in html_content
    assert "Personal task" in html_content
    assert "Work task" not in html_content


def test_report_command_unsupported_format(seeded_report_tasks, tmp_path):
    """An unrecognized output extension is rejected and no file is written."""
    txt_file = tmp_path / "report.txt"

    result = runner.invoke(app, ["report", str(txt_file)])
    assert result.exit_code == 1
    assert "Unsupported format" in result.stdout
    assert not txt_file.exists()


def test_report_command_empty(session, tmp_path):
    """Generating a report with no matching tasks reports there is nothing."""
    empty_file = tmp_path / "empty.md"

    result = runner.invoke(app, ["report", str(empty_file)])
    assert result.exit_code == 0
    assert "No tasks found" in result.stdout
    assert not empty_file.exists()


def test_report_command_invalid_sort(tmp_path):
    """An unrecognized --sort field is rejected."""
    runner.invoke(app, ["add", "Valid Task"])
    md_file = tmp_path / "report.md"

    result = runner.invoke(app, ["report", str(md_file), "--sort", "invalid"])
    assert result.exit_code == 1
    assert "Invalid sort field" in result.stdout


def test_report_command_write_failure(tmp_path):
    """Writing to a path that is a directory surfaces a write failure."""
    dir_path = tmp_path / "dir.md"
    dir_path.mkdir()
    runner.invoke(app, ["add", "Valid Task"])

    result = runner.invoke(app, ["report", str(dir_path)])
    assert result.exit_code == 1
    assert "Failed to write report" in result.stdout


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


def test_auto_initializes_database(monkeypatch, tmp_path):
    """First command auto-inits the DB when the file doesn't exist yet."""
    non_existent = tmp_path / "new_db.sqlite"
    monkeypatch.setattr("odot.database.get_db_path", lambda: non_existent)

    initialized = []
    monkeypatch.setattr(
        "odot.database.create_db_and_tables", lambda: initialized.append(True)
    )

    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert initialized, "create_db_and_tables should have been called"
    assert "Database initialized" in result.stdout
