"""Tests for data models."""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from odot.models import Task, TaskCreate, TaskUpdate


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
