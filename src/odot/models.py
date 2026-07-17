"""Models for odot."""

from datetime import UTC, datetime

from pydantic import field_validator
from sqlmodel import Field, SQLModel


def _normalize_category(value: object) -> object:
    """Lowercase a category on the write seam so casing can't drift.

    Applied to ``TaskCreate``/``TaskUpdate`` (never the ``Task`` table model),
    so new writes converge on one casing per category while legacy rows keep
    whatever casing they already have. Non-string values pass through so
    pydantic raises its normal validation error instead of crashing here.
    """
    return value.lower() if isinstance(value, str) else value


class TaskBase(SQLModel):
    """Base fields for a task."""

    content: str = Field(index=True, min_length=1, max_length=255)
    priority: int = Field(default=1, ge=1, le=3, description="Priority from 1 to 3")
    category: str = Field(
        default="general",
        index=True,
        min_length=1,
        max_length=255,
        description="Free-text category label; normalized to lowercase on write.",
    )


class TaskCreate(TaskBase):
    """Schema used to validate input when creating a new task.

    This is the intentional seam between untrusted input (CLI args, imported
    JSON, etc.) and the ``Task`` table model. It currently mirrors
    ``TaskBase`` with no additional fields, but exists so creation-specific
    validation or fields can be added later without touching ``Task`` itself.
    """

    @field_validator("category", mode="before")
    @classmethod
    def _lower_category(cls, value: object) -> object:
        """Normalize the category to lowercase on creation."""
        return _normalize_category(value)


class TaskUpdate(SQLModel):
    """Model for updating a task. All fields are optional."""

    content: str | None = Field(default=None, min_length=1, max_length=255)
    priority: int | None = Field(
        default=None, ge=1, le=3, description="Priority from 1 to 3"
    )
    category: str | None = Field(default=None, min_length=1, max_length=255)
    is_done: bool | None = Field(default=None)

    @field_validator("category", mode="before")
    @classmethod
    def _lower_category(cls, value: object) -> object:
        """Normalize the category to lowercase on update."""
        return _normalize_category(value)


class Task(TaskBase, table=True):
    """The core Task model.

    This defines the 'tasks' table in SQLite.
    """

    id: int | None = Field(default=None, primary_key=True)
    is_done: bool = Field(default=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: datetime | None = Field(default=None)
