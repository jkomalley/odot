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
