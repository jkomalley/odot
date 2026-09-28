"""Tests that validate external library API contracts.

These tests call the real libraries (not mocked) to ensure parameter
combinations and constraints are respected. This catches issues like
conflicting parameters before code reaches production.
"""

import questionary


def test_select_task_questionary_parameters_valid():
    """Ensure questionary.select() accepts _select_task parameter combinations.

    questionary.select() cannot have both use_search_filter=True and
    use_jk_keys=True simultaneously, as j/k can be part of the search string.
    This test validates that our parameter choices are compatible.

    Regression test for: ValueError: Cannot use j/k keys with prefix filter
    search, since j/k can be part of the prefix.
    """
    # This should NOT raise ValueError
    q = questionary.select(
        "Select a task:",
        choices=[questionary.Choice("Task 1", 1), questionary.Choice("Task 2", 2)],
        instruction="(arrow keys; type to filter)",
        use_search_filter=True,
        use_jk_keys=False,  # Explicitly False to avoid conflict
        show_selected=True,
    )
    # If we got here, the parameters are valid (questionary didn't raise)
    assert q is not None


def test_autocomplete_task_questionary_parameters_valid():
    """Ensure questionary.autocomplete() parameters are valid."""
    q = questionary.autocomplete(
        "Select a task (type to filter):",
        choices=["Task 1", "Task 2"],
        match_middle=True,
    )
    assert q is not None


def test_prompt_priority_questionary_parameters_valid(monkeypatch):
    """Ensure the real questionary.select() accepts _prompt_priority's arguments.

    Only `.ask()` is stubbed (it needs a TTY), so the Choice list and the
    Choice-valued default go through questionary's own validation, which
    raises if the default is not one of the choices.
    """
    from odot.cli import _prompt_priority
    from odot.models import Priority

    monkeypatch.setattr(questionary.Question, "ask", lambda self: Priority.HIGH)
    assert _prompt_priority("Priority:", default=Priority.LOW) is Priority.HIGH
    assert _prompt_priority("New priority:") is Priority.HIGH


def test_prompt_category_questionary_parameters_valid(monkeypatch, session):
    """Ensure the real questionary.select() accepts _prompt_category's arguments.

    Exercises the Separator, the sentinel-valued "New category…" Choice, and a
    preselected default (questionary raises if the default is not a choice).
    """
    from odot import core
    from odot.cli import _prompt_category
    from odot.models import TaskCreate

    core.add_task(db=session, task_data=TaskCreate(content="x", category="work"))
    monkeypatch.setattr(questionary.Question, "ask", lambda self: "work")
    assert _prompt_category(session, "Category:", default="work") == "work"
    assert _prompt_category(session, "Category:", default="general") == "work"
