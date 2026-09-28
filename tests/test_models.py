"""Tests for data models."""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from odot.models import Priority, Task, TaskCreate, TaskUpdate, priority_name


def test_task_creation_valid():
    """Test valid task creation."""
    task = TaskCreate(content="Buy milk", priority=2, category="groceries")
    assert task.content == "Buy milk"
    assert task.priority == 2
    assert task.category == "groceries"


def test_task_creation_defaults():
    """Test default values on task creation."""
    task = TaskCreate(content="Do laundry")
    assert task.priority == 1
    assert task.category == "general"


def test_task_creation_invalid_priority():
    """Test priority validation."""
    with pytest.raises(ValidationError):
        TaskCreate(content="Too urgent", priority=4)

    with pytest.raises(ValidationError):
        TaskCreate(content="Too low", priority=0)


def test_task_creation_invalid_content():
    """Test content length validation."""
    with pytest.raises(ValidationError):
        TaskCreate(content="")  # Empty string

    with pytest.raises(ValidationError):
        TaskCreate(content="a" * 256)  # Exceeds max length


def test_task_creation_invalid_category():
    """An empty category is rejected rather than silently persisted blank."""
    with pytest.raises(ValidationError):
        TaskCreate(content="Valid content", category="")


def test_task_create_normalizes_category_to_lowercase():
    """Categories are lowercased on creation so casing can't drift (see #107)."""
    assert TaskCreate(content="x", category="Work").category == "work"
    assert TaskCreate(content="x", category="WORK").category == "work"


def test_task_create_strips_surrounding_whitespace_from_category():
    """Surrounding whitespace is trimmed alongside lowercasing (see #107)."""
    assert TaskCreate(content="x", category="  Work ").category == "work"


def test_task_create_whitespace_only_category_is_rejected():
    """A whitespace-only category collapses to empty and is rejected (see #107)."""
    with pytest.raises(ValidationError):
        TaskCreate(content="x", category="   ")


def test_task_table_defaults():
    """Test default values for full Task table model."""
    task = Task(content="Database test")
    assert task.id is None
    assert task.is_done is False
    assert task.created_at is not None
    assert task.updated_at is None


def test_task_update_optional_fields():
    """Test that TaskUpdate fields are optional."""
    update_empty = TaskUpdate()
    assert update_empty.content is None
    assert update_empty.priority is None
    assert update_empty.category is None
    assert update_empty.is_done is None

    update_partial = TaskUpdate(priority=3, is_done=True)
    assert update_partial.content is None
    assert update_partial.priority == 3
    assert update_partial.is_done is True


def test_task_update_invalid_content():
    """Test TaskUpdate content length validation (see #49)."""
    with pytest.raises(ValidationError):
        TaskUpdate(content="")  # min_length=1

    with pytest.raises(ValidationError):
        TaskUpdate(content="a" * 256)  # max_length=255


def test_task_update_invalid_priority():
    """Test TaskUpdate priority range validation (see #49)."""
    with pytest.raises(ValidationError):
        TaskUpdate(priority=0)  # ge=1

    with pytest.raises(ValidationError):
        TaskUpdate(priority=4)  # le=3


def test_task_update_valid_partial_updates():
    """Test that valid partial TaskUpdate values are accepted (see #49)."""
    content_only = TaskUpdate(content="Updated content")
    assert content_only.content == "Updated content"
    assert content_only.priority is None

    priority_only = TaskUpdate(priority=1)
    assert priority_only.priority == 1

    boundary_priority = TaskUpdate(priority=3)
    assert boundary_priority.priority == 3

    category_only = TaskUpdate(category="errands")
    assert category_only.category == "errands"

    done_only = TaskUpdate(is_done=False)
    assert done_only.is_done is False


def test_task_update_normalizes_category_to_lowercase():
    """Categories are lowercased on update so casing can't drift (see #107)."""
    assert TaskUpdate(category="Work").category == "work"


def test_task_update_strips_surrounding_whitespace_from_category():
    """Surrounding whitespace is trimmed on update alongside lowercasing (see #107)."""
    assert TaskUpdate(category="  Work ").category == "work"


def test_task_update_category_none_passes_through():
    """An explicit None category must not crash the normalizer (see #107)."""
    assert TaskUpdate(category=None).category is None


# --------------------------------------------------------------------------- #
# Property-based tests (Hypothesis)
# --------------------------------------------------------------------------- #


@given(content=st.text(min_size=1, max_size=255))
def test_task_create_content_within_bounds_accepted(content):
    """Any content within [1, 255] chars should be accepted by TaskCreate."""
    task = TaskCreate(content=content)
    assert task.content == content


@given(content=st.text(min_size=256, max_size=300))
def test_task_create_content_over_max_rejected(content):
    """Content longer than 255 chars should always be rejected."""
    with pytest.raises(ValidationError):
        TaskCreate(content=content)


@given(priority=st.integers(min_value=1, max_value=3))
def test_task_create_priority_within_bounds_accepted(priority):
    """Any priority within [1, 3] should be accepted by TaskCreate."""
    task = TaskCreate(content="valid content", priority=priority)
    assert task.priority == priority


@given(
    priority=st.integers(min_value=-100, max_value=100).filter(lambda p: p < 1 or p > 3)
)
def test_task_create_priority_out_of_bounds_rejected(priority):
    """Any priority outside [1, 3] should always be rejected."""
    with pytest.raises(ValidationError):
        TaskCreate(content="valid content", priority=priority)


@given(priority=st.integers(min_value=1, max_value=3))
def test_task_update_priority_within_bounds_accepted(priority):
    """Any priority within [1, 3] should be accepted by TaskUpdate."""
    update = TaskUpdate(priority=priority)
    assert update.priority == priority


@given(
    priority=st.integers(min_value=-100, max_value=100).filter(lambda p: p < 1 or p > 3)
)
def test_task_update_priority_out_of_bounds_rejected(priority):
    """Any priority outside [1, 3] should always be rejected by TaskUpdate."""
    with pytest.raises(ValidationError):
        TaskUpdate(priority=priority)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("low", Priority.LOW),
        ("Medium", Priority.MEDIUM),
        (" HIGH ", Priority.HIGH),
        ("2", Priority.MEDIUM),
        (" 3 ", Priority.HIGH),
        (1, Priority.LOW),
        (Priority.HIGH, Priority.HIGH),
    ],
)
def test_priority_parse_accepts_names_and_numbers(raw, expected):
    """Names are case/whitespace-insensitive; legacy 1-3 still parse (#159)."""
    assert Priority.parse(raw) is expected


@pytest.mark.parametrize("raw", ["urgent", "", "0", "4", 0, 4, 2.5, None])
def test_priority_parse_rejects_unknown_values(raw):
    """Anything else raises, and the message advertises the names only."""
    with pytest.raises(ValueError, match="low, medium, or high"):
        Priority.parse(raw)


def test_priority_label():
    """Each level has a capitalized human label."""
    assert [p.label for p in Priority] == ["Low", "Medium", "High"]


def test_priority_name_in_range():
    """priority_name renders a stored int as its label."""
    assert priority_name(2) == "Medium"


def test_priority_name_out_of_range_falls_back_to_number():
    """Malformed stored values render as the bare number instead of crashing."""
    assert priority_name(7) == "7"


def test_task_create_accepts_priority_name():
    """TaskCreate converts a name to its stored int (e.g. from JSON import)."""
    assert TaskCreate(content="x", priority="High").priority == 3


def test_task_update_accepts_priority_name():
    """TaskUpdate converts a name to its stored int."""
    assert TaskUpdate(priority=" low ").priority == 1


@pytest.mark.parametrize("model", [TaskCreate, TaskUpdate])
def test_unknown_priority_name_rejected(model):
    """An unknown name surfaces as a normal pydantic ValidationError."""
    with pytest.raises(ValidationError):
        model(content="x", priority="urgent")
