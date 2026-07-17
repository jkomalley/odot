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
        # Non-None so main_callback's bare-invocation branch (#61) is skipped;
        # that branch is exercised separately by the bare-invocation tests.
        invoked_subcommand = "list"

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


def test_add_command_out_of_range_priority_reports_clean_error():
    """An out-of-range --priority is a clean CLI error, not a raw traceback."""
    result = runner.invoke(app, ["add", "Test Task", "--priority", "99"])
    assert result.exit_code == 1
    assert "ValidationError" not in result.stdout
    assert "priority" in result.stdout.lower()


def test_json_add_out_of_range_priority_errors_on_stderr():
    """`add --json` with an invalid priority errors to stderr, not a traceback."""
    result = runner.invoke(app, ["add", "Test Task", "--priority", "99", "--json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "ValidationError" not in result.stderr
    assert "priority" in result.stderr.lower()


def test_add_command_empty_category_is_rejected():
    """An explicit empty --category is a clean CLI error, not a blank category."""
    result = runner.invoke(app, ["add", "Test Task", "--category", ""])
    assert result.exit_code == 1
    assert "ValidationError" not in result.stdout
    assert "category" in result.stdout.lower()


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


def test_prompt_task_selection_select_labels_include_metadata(monkeypatch, session):
    """Below the threshold, select choices carry category + priority metadata."""
    from odot.cli import prompt_task_selection

    runner.invoke(app, ["add", "Buy groceries", "-c", "home", "-p", "3"])

    captured: dict = {}

    class MockSelect:
        def ask(self):
            return 1

    def fake_select(*args, **kwargs):
        captured["kwargs"] = kwargs
        return MockSelect()

    monkeypatch.setattr("questionary.select", fake_select)

    assert prompt_task_selection(session, "update") == 1

    title = captured["kwargs"]["choices"][0].title
    assert "home" in title  # category column
    assert "High" in title  # plain-text priority label
    assert "●" in title  # priority dot glyph
    # The instruction hint is surfaced so type-to-filter is discoverable.
    assert captured["kwargs"]["instruction"] == "(arrow keys; type to filter)"
    assert captured["kwargs"]["use_search_filter"] is True


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


def _seed_tasks(count: int) -> None:
    """Seed `count` tasks so the autocomplete threshold branch is exercised."""
    for i in range(count):
        runner.invoke(app, ["add", f"Task number {i}"])


def test_prompt_task_selection_autocomplete_at_threshold(monkeypatch, session):
    """At exactly AUTOCOMPLETE_THRESHOLD tasks, the autocomplete branch is used."""
    from odot.cli import AUTOCOMPLETE_THRESHOLD, prompt_task_selection

    _seed_tasks(AUTOCOMPLETE_THRESHOLD)

    captured: dict = {}

    class MockAutocomplete:
        def ask(self):
            # Echo back the label for task id 1 so the mapping resolves it.
            return captured["kwargs"]["choices"][0]

    def fake_autocomplete(*args, **kwargs):
        captured["kwargs"] = kwargs
        return MockAutocomplete()

    # If select were (wrongly) chosen, this would raise and fail the test.
    def boom(*args, **kwargs):
        raise AssertionError("select should not be used at the threshold")

    monkeypatch.setattr("questionary.autocomplete", fake_autocomplete)
    monkeypatch.setattr("questionary.select", boom)

    result = prompt_task_selection(session, "select")
    assert result == 1
    assert captured["kwargs"]["match_middle"] is True


def test_prompt_task_selection_autocomplete_invalid_answer(monkeypatch, session):
    """A free-text autocomplete answer that maps to no task exits with code 1."""
    import typer

    from odot.cli import AUTOCOMPLETE_THRESHOLD, prompt_task_selection

    _seed_tasks(AUTOCOMPLETE_THRESHOLD)

    class MockAutocomplete:
        def ask(self):
            return "not a real task label"

    monkeypatch.setattr("questionary.autocomplete", lambda *a, **k: MockAutocomplete())

    with pytest.raises(typer.Exit) as exc_info:
        prompt_task_selection(session, "select")
    assert exc_info.value.exit_code == 1


def test_prompt_task_selection_autocomplete_cancel(monkeypatch, session):
    """Cancelling the autocomplete prompt (ask returns None) exits."""
    import typer

    from odot.cli import AUTOCOMPLETE_THRESHOLD, prompt_task_selection

    _seed_tasks(AUTOCOMPLETE_THRESHOLD)

    class MockAutocompleteCancelled:
        def ask(self):
            return None

    monkeypatch.setattr(
        "questionary.autocomplete", lambda *a, **k: MockAutocompleteCancelled()
    )

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


def test_add_uppercase_category_is_found_by_lowercase_filter():
    """An uppercase-added category is matched by a lowercase filter (see #107)."""
    runner.invoke(app, ["add", "Buy milk", "--category", "Work"])
    result = runner.invoke(app, ["list", "--category", "work"])
    assert result.exit_code == 0
    assert "Buy milk" in result.stdout


def test_add_lowercase_category_is_found_by_uppercase_filter():
    """A lowercase-added category is matched by an uppercase filter (see #107)."""
    runner.invoke(app, ["add", "Buy milk", "--category", "work"])
    result = runner.invoke(app, ["list", "--category", "Work"])
    assert result.exit_code == 0
    assert "Buy milk" in result.stdout


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
    """An unrecognized --sort field is rejected at parse time by Typer (exit 2)."""
    runner.invoke(app, ["add", "Task A"])

    result = runner.invoke(app, ["list", "--sort", "invalid_field"])
    assert result.exit_code == 2
    assert "invalid_field" in result.output


def test_list_command_empty(session):
    """An empty database shows an onboarding hint rather than a bare message (#58)."""
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No tasks yet" in result.stdout
    assert "odot add" in result.stdout


def test_list_command_empty_filtered_by_category():
    """A category filter that matches nothing names the filter and true total (#58)."""
    runner.invoke(app, ["add", "Task A", "--category", "work"])

    result = runner.invoke(app, ["list", "--category", "personal"])
    assert result.exit_code == 0
    assert 'No tasks found in "personal"' in result.stdout
    assert "1 total tasks" in result.stdout


def test_list_command_empty_filtered_by_done():
    """A --done filter that matches nothing reports the status and true total (#58)."""
    runner.invoke(app, ["add", "Task A"])

    result = runner.invoke(app, ["list", "--done"])
    assert result.exit_code == 0
    assert "No completed tasks found" in result.stdout
    assert "1 total tasks" in result.stdout


def test_list_command_empty_filtered_by_both():
    """Combined category and status filters both appear in the empty message (#58)."""
    runner.invoke(app, ["add", "Task A", "--category", "work"])
    runner.invoke(app, ["update", "1", "--done"])

    # Task A is done, so filtering to pending work tasks matches nothing.
    result = runner.invoke(app, ["list", "--category", "work", "--todo"])
    assert result.exit_code == 0
    assert "No pending tasks found" in result.stdout
    assert '"work"' in result.stdout


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
    assert "Updated task #1" in result.stdout
    # Diff lines (#57) echo the specific fields that changed.
    assert "content: Old Task → New Task" in result.stdout
    assert "priority: 1 → 2" in result.stdout
    assert "status: Pending → Done" in result.stdout

    verify = runner.invoke(app, ["show", "1"])
    assert "New Task" in verify.stdout
    assert "Done" in verify.stdout


def test_update_command_single_field():
    """A single --category flag updates only that field."""
    runner.invoke(app, ["add", "Old Task"])

    result = runner.invoke(app, ["update", "1", "--category", "work"])
    assert result.exit_code == 0
    assert "Updated task #1" in result.stdout
    assert "category: general → work" in result.stdout
    # Unchanged fields should not appear in the diff.
    assert "content:" not in result.stdout


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
    assert "Updated task #1" in result.stdout


def test_update_command_missing_task():
    """Updating a nonexistent task should report not-found."""
    result = runner.invoke(app, ["update", "999", "--done"])
    assert result.exit_code == 1
    assert "Task 999 not found" in result.stdout


def test_update_command_out_of_range_priority_reports_clean_error():
    """An out-of-range --priority is a clean CLI error, not a raw traceback."""
    runner.invoke(app, ["add", "Task to update"])
    result = runner.invoke(app, ["update", "1", "--priority", "0"])
    assert result.exit_code == 1
    assert "ValidationError" not in result.stdout
    assert "priority" in result.stdout.lower()


def test_json_update_out_of_range_priority_errors_on_stderr():
    """`update --json` with an invalid priority errors to stderr cleanly."""
    runner.invoke(app, ["add", "Task to update"])
    result = runner.invoke(app, ["update", "1", "--priority", "0", "--json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "ValidationError" not in result.stderr
    assert "priority" in result.stderr.lower()


def test_update_command_empty_category_is_rejected():
    """An explicit empty --category on update is a clean CLI error."""
    runner.invoke(app, ["add", "Task to update"])
    result = runner.invoke(app, ["update", "1", "--category", ""])
    assert result.exit_code == 1
    assert "ValidationError" not in result.stdout
    assert "category" in result.stdout.lower()


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
    assert "Updated task #1" in result.stdout
    assert "content: Partial task → Only content changed" in result.stdout


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
    assert "Updated task #1" in result.stdout
    # Priority was never actually set, so no diff line for it appears.
    assert "priority:" not in result.stdout


def test_done_command():
    """Marking a task done via the done shortcut updates its status."""
    runner.invoke(app, ["add", "Finish me"])

    result = runner.invoke(app, ["done", "1"])
    assert result.exit_code == 0
    assert "Marked done" in result.stdout
    assert "Finish me" in result.stdout

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
    assert "Marked done" in result.stdout


def test_undo_command():
    """Re-opening a completed task via undo resets its status."""
    runner.invoke(app, ["add", "Already done"])
    runner.invoke(app, ["done", "1"])

    result = runner.invoke(app, ["undo", "1"])
    assert result.exit_code == 0
    assert "Re-opened" in result.stdout
    assert "Already done" in result.stdout

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
    assert "Re-opened" in result.stdout


def test_rm_command_with_force_flag():
    """The --force flag deletes a task without a confirmation prompt."""
    runner.invoke(app, ["add", "Delete me"])

    result = runner.invoke(app, ["rm", "1", "--force"])
    assert result.exit_code == 0
    assert "Deleted task #1" in result.stdout
    assert "Delete me" in result.stdout

    verify = runner.invoke(app, ["show", "1"])
    assert verify.exit_code == 1


def test_rm_command_aborted_confirmation():
    """Declining the confirmation prompt leaves the task in place."""
    runner.invoke(app, ["add", "Delete me too"])

    result = runner.invoke(app, ["rm", "1"], input="n\n")
    assert result.exit_code == 1
    # Task content is echoed in the prompt (#57) so users confirm by what
    # they remember, not by numeric id.
    assert 'Delete "Delete me too" (task #1)?' in result.stdout


def test_rm_command_interactive_prompt_confirmed(monkeypatch):
    """Confirmed deletion via the interactive task-id prompt removes the task."""
    runner.invoke(app, ["add", "Delete me too"])
    monkeypatch.setattr("odot.cli.prompt_task_selection", lambda db, action: 1)

    result = runner.invoke(app, ["rm"], input="y\n")
    assert result.exit_code == 0
    assert "Deleted task #1" in result.stdout


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
    assert "Cleaned 2 completed tasks." in result.stdout

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
    assert "Exported 1 tasks" in result.stdout

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
    assert "Exported" not in result.stdout


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
    assert "Imported 1 tasks" in result.stdout


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
    assert "Imported 1 tasks" in result.stdout

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
    assert "Generated report" in result.stdout
    assert md_file.exists()

    md_content = md_file.read_text()
    assert "# Odot Task Report" in md_content
    assert "## work" in md_content
    assert "- [ ] Work task (Priority: 3)" in md_content
    assert "## personal" in md_content
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
    """An unrecognized --sort field is rejected at parse time by Typer (exit 2)."""
    runner.invoke(app, ["add", "Valid Task"])
    md_file = tmp_path / "report.md"

    result = runner.invoke(app, ["report", str(md_file), "--sort", "invalid"])
    assert result.exit_code == 2
    assert "invalid" in result.output


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


# --------------------------------------------------------------------------- #
# SortField / core.VALID_SORT_FIELDS parity (#61 refactor prerequisite)
# --------------------------------------------------------------------------- #


def test_sort_field_enum_matches_core_valid_sort_fields():
    """SortField values must stay in sync with core.VALID_SORT_FIELDS."""
    from odot import core
    from odot.cli import SortField

    assert {f.value for f in SortField} == set(core.VALID_SORT_FIELDS)


# --------------------------------------------------------------------------- #
# #54: priority indicators
# --------------------------------------------------------------------------- #


def test_list_command_shows_priority_dot_indicators():
    """Priorities render as colored dot indicators, not bare numbers (#54)."""
    runner.invoke(app, ["add", "Low priority", "-p", "1"])
    runner.invoke(app, ["add", "Med priority", "-p", "2"])
    runner.invoke(app, ["add", "High priority", "-p", "3"])

    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "Low" in result.stdout
    assert "Med" in result.stdout
    assert "High" in result.stdout
    assert "●" in result.stdout


# --------------------------------------------------------------------------- #
# #55: list summary footer
# --------------------------------------------------------------------------- #


def test_list_command_summary_footer_counts():
    """The footer beneath the table reports total/pending/done counts (#55)."""
    runner.invoke(app, ["add", "Task A"])
    runner.invoke(app, ["add", "Task B"])
    runner.invoke(app, ["update", "2", "--done"])

    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "2 tasks (1 pending, 1 done)" in result.stdout


def test_list_command_summary_footer_reflects_category_filter():
    """The footer names the active category filter (#55)."""
    runner.invoke(app, ["add", "Task A", "--category", "work"])
    runner.invoke(app, ["add", "Task B", "--category", "personal"])

    result = runner.invoke(app, ["list", "--category", "work"])
    assert result.exit_code == 0
    assert '1 tasks in "work" (1 pending, 0 done)' in result.stdout


# --------------------------------------------------------------------------- #
# #56: relative time in `show`
# --------------------------------------------------------------------------- #


def test_show_command_displays_relative_time_alongside_absolute():
    """`show` displays a relative-time hint next to the absolute timestamp (#56)."""
    runner.invoke(app, ["add", "Show me"])

    result = runner.invoke(app, ["show", "1"])
    assert result.exit_code == 0
    assert "ago" in result.stdout or "just now" in result.stdout


def test_show_command_updated_at_includes_relative_time():
    """The Updated At row also carries a relative-time annotation (#56)."""
    runner.invoke(app, ["add", "Show me"])
    runner.invoke(app, ["update", "1", "-p", "3"])

    result = runner.invoke(app, ["show", "1"])
    assert result.exit_code == 0
    assert result.stdout.count("ago") + result.stdout.count("just now") >= 2


# --------------------------------------------------------------------------- #
# #57: richer confirmations
# --------------------------------------------------------------------------- #


def test_add_command_confirmation_includes_full_context():
    """Add's confirmation echoes priority/category so users skip a follow-up show."""
    result = runner.invoke(
        app, ["add", "Buy groceries", "--priority", "2", "--category", "work"]
    )
    assert result.exit_code == 0
    assert "Buy groceries" in result.stdout
    assert "Priority: 2" in result.stdout
    assert "Category: work" in result.stdout


def test_clean_command_no_completed_tasks_uses_warning_style():
    """The 'nothing to clean' message is a yellow warning, not a plain notice."""
    runner.invoke(app, ["add", "Keep me 1"])

    result = runner.invoke(app, ["clean", "--force"])
    assert result.exit_code == 0
    assert "No completed tasks to delete." in result.stdout


# --------------------------------------------------------------------------- #
# #58: count command + empty states
# --------------------------------------------------------------------------- #


def test_count_command_all_tasks():
    """`odot count` with no filters reports total/pending/done."""
    runner.invoke(app, ["add", "Task A"])
    runner.invoke(app, ["add", "Task B"])
    runner.invoke(app, ["update", "2", "--done"])

    result = runner.invoke(app, ["count"])
    assert result.exit_code == 0
    assert "2 tasks (1 pending, 1 done)" in result.stdout


def test_count_command_todo_filter():
    """`odot count --todo` collapses to a single pending count."""
    runner.invoke(app, ["add", "Task A"])
    runner.invoke(app, ["add", "Task B"])
    runner.invoke(app, ["update", "2", "--done"])

    result = runner.invoke(app, ["count", "--todo"])
    assert result.exit_code == 0
    assert "1 pending task" in result.stdout


def test_count_command_done_and_category_filter():
    """`odot count --done --category work` reads as 'N completed work task(s)'."""
    runner.invoke(app, ["add", "Task A", "--category", "work"])
    runner.invoke(app, ["add", "Task B", "--category", "work"])
    runner.invoke(app, ["update", "1", "--done"])

    result = runner.invoke(app, ["count", "--done", "--category", "work"])
    assert result.exit_code == 0
    assert "1 completed work task" in result.stdout


def test_count_command_todo_filter_plural():
    """`odot count --todo` pluralizes 'tasks' when the count isn't 1."""
    runner.invoke(app, ["add", "Task A"])
    runner.invoke(app, ["add", "Task B"])
    runner.invoke(app, ["add", "Task C"])
    runner.invoke(app, ["update", "3", "--done"])

    result = runner.invoke(app, ["count", "--todo"])
    assert result.exit_code == 0
    assert "2 pending tasks" in result.stdout


def test_count_command_empty_database():
    """Counting an empty database reports zero without erroring."""
    result = runner.invoke(app, ["count"])
    assert result.exit_code == 0
    assert "0 tasks (0 pending, 0 done)" in result.stdout


def test_count_command_with_category_no_status_filter():
    """`odot count --category work` reports the pending/done breakdown for work."""
    runner.invoke(app, ["add", "Task A", "--category", "work"])

    result = runner.invoke(app, ["count", "--category", "work"])
    assert result.exit_code == 0
    assert '1 tasks in "work" (1 pending, 0 done)' in result.stdout


# --------------------------------------------------------------------------- #
# #60: search highlight
# --------------------------------------------------------------------------- #


def test_search_command_highlights_match():
    """Search results highlight the matched phrase using rich styling (#60)."""
    runner.invoke(app, ["add", "Buy groceries for dinner"])

    result = runner.invoke(app, ["search", "groceries"])
    assert result.exit_code == 0
    assert "groceries" in result.stdout


def test_search_command_is_case_insensitive():
    """Search matches regardless of case, per core's icontains-based lookup."""
    runner.invoke(app, ["add", "Buy Groceries for dinner"])

    result = runner.invoke(app, ["search", "groceries"])
    assert result.exit_code == 0
    assert "Groceries" in result.stdout


def test_search_command_content_with_brackets_not_broken_by_markup():
    """Content containing literal brackets renders safely (rich Text, not markup)."""
    runner.invoke(app, ["add", "Buy [urgent] milk"])

    result = runner.invoke(app, ["search", "milk"])
    assert result.exit_code == 0
    assert "[urgent]" in result.stdout


# --------------------------------------------------------------------------- #
# #61: bare invocation shows the task list
# --------------------------------------------------------------------------- #


def test_bare_invocation_shows_list_with_tasks():
    """Running `odot` with no subcommand shows the task list (#61)."""
    runner.invoke(app, ["add", "Task A"])

    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Task A" in result.stdout
    assert "Odot Tasks" in result.stdout


def test_bare_invocation_shows_onboarding_on_empty_db(session):
    """Running `odot` against an empty database shows the onboarding hint (#61)."""
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "No tasks yet" in result.stdout


def test_bare_invocation_still_initializes_session_lifecycle(tmp_path, monkeypatch):
    """Bare invocation still auto-inits the DB and closes the session on exit."""
    non_existent = tmp_path / "bare_db.sqlite"
    monkeypatch.setattr("odot.database.get_db_path", lambda: non_existent)

    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Database initialized" in result.stdout


def test_help_still_works_with_invoke_without_command():
    """`--help` continues to short-circuit to the help page (#61)."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "A minimalist CLI task manager." in result.stdout


def test_explicit_subcommand_does_not_trigger_bare_list():
    """Invoking a real subcommand does not also print the bare-invocation list."""
    runner.invoke(app, ["add", "Task A"])

    result = runner.invoke(app, ["show", "1"])
    assert result.exit_code == 0
    assert "Odot Tasks" not in result.stdout


# --------------------------------------------------------------------------- #
# --json output (#62)
# --------------------------------------------------------------------------- #
def _json_out(result):
    """Parse a command's stdout as JSON, asserting stdout is the sole channel."""
    return json.loads(result.stdout)


def test_json_add_returns_task_object():
    """`add --json` emits a single task object with the export schema fields."""
    result = runner.invoke(app, ["add", "JSON task", "-p", "2", "-c", "work", "--json"])
    assert result.exit_code == 0
    data = _json_out(result)
    assert data["id"] == 1
    assert data["content"] == "JSON task"
    assert data["priority"] == 2
    assert data["category"] == "work"
    assert data["is_done"] is False
    # Schema mirrors export exactly.
    assert set(data) == {
        "id",
        "content",
        "priority",
        "category",
        "is_done",
        "created_at",
        "updated_at",
    }


def test_json_add_missing_content_exits_two():
    """`add --json` with no content errors on stderr and exits 2 (never prompts)."""
    result = runner.invoke(app, ["add", "--json"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "content is required" in result.stderr


def test_json_global_flag_before_subcommand():
    """The global callback flag (`odot --json add ...`) also enables JSON."""
    result = runner.invoke(app, ["--json", "add", "Global flag task"])
    assert result.exit_code == 0
    assert _json_out(result)["content"] == "Global flag task"


def test_json_list_empty_is_empty_array():
    """`list --json` with no tasks emits an empty array, not prose."""
    result = runner.invoke(app, ["list", "--json"])
    assert result.exit_code == 0
    assert _json_out(result) == []


def test_json_list_returns_array():
    """`list --json` returns a JSON array of every task."""
    runner.invoke(app, ["add", "Task A"])
    runner.invoke(app, ["add", "Task B"])

    result = runner.invoke(app, ["list", "--json"])
    assert result.exit_code == 0
    data = _json_out(result)
    assert [t["content"] for t in data] == ["Task A", "Task B"]


def test_json_bare_invocation_emits_list_json():
    """Bare `odot --json` falls through to the list command's JSON array."""
    runner.invoke(app, ["add", "Bare task"])

    result = runner.invoke(app, ["--json"])
    assert result.exit_code == 0
    assert [t["content"] for t in _json_out(result)] == ["Bare task"]


def test_json_show_returns_object():
    """`show --json` returns the single matching task object."""
    runner.invoke(app, ["add", "Show me"])

    result = runner.invoke(app, ["show", "1", "--json"])
    assert result.exit_code == 0
    assert _json_out(result)["content"] == "Show me"


def test_json_show_missing_task_errors_on_stderr():
    """`show --json` on a missing id errors to stderr with exit 1, clean stdout."""
    result = runner.invoke(app, ["show", "999", "--json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Task 999 not found" in result.stderr


def test_json_show_missing_id_exits_two():
    """`show --json` without an id errors (no interactive prompt) and exits 2."""
    result = runner.invoke(app, ["show", "--json"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "task id is required" in result.stderr


def test_json_count_returns_breakdown():
    """`count --json` returns a total/pending/done breakdown object."""
    runner.invoke(app, ["add", "Task A"])
    runner.invoke(app, ["add", "Task B"])
    runner.invoke(app, ["done", "1"])

    result = runner.invoke(app, ["count", "--json"])
    assert result.exit_code == 0
    assert _json_out(result) == {"total": 2, "pending": 1, "done": 1}


def test_json_search_returns_array():
    """`search --json` returns a JSON array of matching tasks."""
    runner.invoke(app, ["add", "Findable phrase"])
    runner.invoke(app, ["add", "Unrelated"])

    result = runner.invoke(app, ["search", "Findable", "--json"])
    assert result.exit_code == 0
    data = _json_out(result)
    assert [t["content"] for t in data] == ["Findable phrase"]


def test_json_search_no_matches_is_empty_array():
    """`search --json` with no matches emits an empty array."""
    runner.invoke(app, ["add", "Task A"])

    result = runner.invoke(app, ["search", "nomatch", "--json"])
    assert result.exit_code == 0
    assert _json_out(result) == []


def test_json_update_returns_task():
    """`update --json` returns the updated task object."""
    runner.invoke(app, ["add", "Old"])

    result = runner.invoke(app, ["update", "1", "--content", "New", "--json"])
    assert result.exit_code == 0
    assert _json_out(result)["content"] == "New"


def test_json_update_no_fields_exits_two():
    """`update --json` with no field flags errors (no prompt) and exits 2."""
    runner.invoke(app, ["add", "Old"])

    result = runner.invoke(app, ["update", "1", "--json"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "field flag is required" in result.stderr


def test_json_update_missing_task_errors():
    """`update --json` on a missing task errors to stderr with exit 1."""
    result = runner.invoke(app, ["update", "999", "--done", "--json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Task 999 not found" in result.stderr


def test_json_done_returns_task():
    """`done --json` returns the completed task object."""
    runner.invoke(app, ["add", "Finish me"])

    result = runner.invoke(app, ["done", "1", "--json"])
    assert result.exit_code == 0
    data = _json_out(result)
    assert data["is_done"] is True


def test_json_done_missing_task_errors():
    """`done --json` on a missing task errors to stderr with exit 1."""
    result = runner.invoke(app, ["done", "999", "--json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Task 999 not found" in result.stderr


def test_json_undo_returns_task():
    """`undo --json` returns the re-opened task object."""
    runner.invoke(app, ["add", "Done then undone"])
    runner.invoke(app, ["done", "1"])

    result = runner.invoke(app, ["undo", "1", "--json"])
    assert result.exit_code == 0
    assert _json_out(result)["is_done"] is False


def test_json_undo_missing_task_errors():
    """`undo --json` on a missing task errors to stderr with exit 1."""
    result = runner.invoke(app, ["undo", "999", "--json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Task 999 not found" in result.stderr


def test_json_rm_force_returns_deleted_count():
    """`rm --force --json` returns a deleted-count object."""
    runner.invoke(app, ["add", "Delete me"])

    result = runner.invoke(app, ["rm", "1", "--force", "--json"])
    assert result.exit_code == 0
    assert _json_out(result) == {"deleted": 1}


def test_json_rm_without_force_exits_two():
    """`rm --json` without --force errors (no confirm prompt) and exits 2."""
    runner.invoke(app, ["add", "Delete me"])

    result = runner.invoke(app, ["rm", "1", "--json"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "--force is required" in result.stderr


def test_json_rm_missing_id_exits_two():
    """`rm --json` without an id errors (no prompt) and exits 2."""
    result = runner.invoke(app, ["rm", "--json"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "task id is required" in result.stderr


def test_json_rm_missing_task_errors():
    """`rm --force --json` on a missing task errors to stderr with exit 1."""
    result = runner.invoke(app, ["rm", "999", "--force", "--json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Task 999 not found" in result.stderr


def test_json_clean_returns_deleted_count():
    """`clean --force --json` returns a deleted-count object."""
    runner.invoke(app, ["add", "Keep"])
    runner.invoke(app, ["add", "Remove"])
    runner.invoke(app, ["done", "2"])

    result = runner.invoke(app, ["clean", "--force", "--json"])
    assert result.exit_code == 0
    assert _json_out(result) == {"deleted": 1}


def test_json_clean_without_force_exits_two():
    """`clean --json` without --force errors and exits 2."""
    result = runner.invoke(app, ["clean", "--json"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "--force is required" in result.stderr


def test_json_purge_returns_deleted_count():
    """`purge --force --json` returns a deleted-count object, no warning prose."""
    runner.invoke(app, ["add", "Task A"])
    runner.invoke(app, ["add", "Task B"])

    result = runner.invoke(app, ["purge", "--force", "--json"])
    assert result.exit_code == 0
    assert _json_out(result) == {"deleted": 2}


def test_json_purge_without_force_exits_two():
    """`purge --json` without --force errors and exits 2 with no warning on stdout."""
    runner.invoke(app, ["add", "Task A"])

    result = runner.invoke(app, ["purge", "--json"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "--force is required" in result.stderr


def test_json_import_returns_imported_count(tmp_path):
    """`import --json` returns an imported-count object."""
    import_file = tmp_path / "import.json"
    payload = [{"content": "Imported task", "priority": 1, "is_done": False}]
    with import_file.open("w") as f:
        json.dump(payload, f)

    result = runner.invoke(app, ["import", str(import_file), "--json"])
    assert result.exit_code == 0
    assert _json_out(result) == {"imported": 1}


def test_json_import_clear_exits_two(tmp_path):
    """`import --clear --json` cannot confirm the wipe and exits 2."""
    import_file = tmp_path / "import.json"
    payload = [{"content": "Imported task", "priority": 1, "is_done": False}]
    with import_file.open("w") as f:
        json.dump(payload, f)

    result = runner.invoke(app, ["import", str(import_file), "--clear", "--json"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "--clear cannot be confirmed" in result.stderr


def test_json_import_malformed_errors_on_stderr(tmp_path):
    """`import --json` on malformed JSON errors to stderr with exit 1."""
    bad = tmp_path / "bad.json"
    bad.write_text("not json")

    result = runner.invoke(app, ["import", str(bad), "--json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Failed to import tasks" in result.stderr


def test_json_export_flag_is_ignored(tmp_path):
    """`export --json` is accepted but produces export's normal file artifact."""
    runner.invoke(app, ["add", "Export me"])
    out = tmp_path / "export.json"

    result = runner.invoke(app, ["--json", "export", str(out)])
    assert result.exit_code == 0
    with out.open() as f:
        assert json.load(f)[0]["content"] == "Export me"


def test_json_report_flag_is_ignored(tmp_path):
    """`report --json` is accepted but still writes its Markdown artifact."""
    runner.invoke(app, ["add", "Report me"])
    out = tmp_path / "report.md"

    result = runner.invoke(app, ["--json", "report", str(out)])
    assert result.exit_code == 0
    assert "Report me" in out.read_text()


def test_json_auto_init_notice_goes_to_stderr(tmp_path, monkeypatch):
    """Under --json, the auto-init notice goes to stderr so stdout stays JSON."""
    non_existent = tmp_path / "auto_init.sqlite"
    monkeypatch.setattr("odot.database.get_db_path", lambda: non_existent)

    result = runner.invoke(app, ["--json", "list"])
    assert result.exit_code == 0
    assert _json_out(result) == []
    assert "Database initialized" in result.stderr
    assert "Database initialized" not in result.stdout
