"""Tests for data models."""

import pytest
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


def test_task_table_defaults():
    """Test default values for full Task table model."""
    task = Task(content="Database test")
    assert task.id is None
    assert task.is_done is False
    assert task.created_at is not None


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
