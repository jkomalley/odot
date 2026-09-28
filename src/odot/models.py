"""Models for odot."""

from datetime import UTC, datetime
from enum import IntEnum
from typing import Self

from pydantic import field_validator
from sqlmodel import Field, SQLModel


def _normalize_category(value: object) -> object:
    """Trim and lowercase a category on the write seam so casing can't drift.

    Applied to ``TaskCreate``/``TaskUpdate`` (never the ``Task`` table model),
    so new writes converge on one casing per category while legacy rows keep
    whatever casing they already have. Surrounding whitespace is stripped for
    the same reason casing is normalized: ``"work "`` and ``"work"`` should not
    become distinct categories. A whitespace-only value collapses to ``""`` and
    is then rejected by ``min_length=1``. Non-string values pass through so
    pydantic raises its normal validation error instead of crashing here.
    """
    return value.strip().lower() if isinstance(value, str) else value


class Priority(IntEnum):
    """Task priority levels, stored in the database as their int values.

    The column stays a plain ``INTEGER`` (see ``TaskBase.priority``) rather than
    a SQLAlchemy ``Enum``, which would persist member *names* and break existing
    rows; this enum is only the vocabulary for input parsing and display.
    """

    LOW = 1
    MEDIUM = 2
    HIGH = 3

    @property
    def label(self) -> str:
        """Human-facing name, e.g. ``"Medium"``."""
        return self.name.capitalize()

    @classmethod
    def parse(cls, value: object) -> Self:
        """Parse a priority name (any case) or a legacy 1-3 number.

        Numbers are still accepted so scripts written against the old numeric
        ``-p`` flag keep working, but only the names are advertised.

        Args:
            value: A ``Priority``, an int, a numeric string, or a name.

        Returns:
            The matching ``Priority`` member.

        Raises:
            ValueError: If ``value`` names no priority level.
        """
        if isinstance(value, str):
            text = value.strip()
            if text.upper() in cls.__members__:
                return cls[text.upper()]
            # ASCII only: isdecimal() alone also admits e.g. Arabic-Indic digits.
            value = int(text) if text.isascii() and text.isdecimal() else text
        if isinstance(value, int) and value in cls._value2member_map_:
            return cls(value)
        msg = f"{value!r} is not low, medium, or high."
        raise ValueError(msg)


def priority_name(priority: int) -> str:
    """Render a stored priority as its label, e.g. ``2`` -> ``"Medium"``.

    Out-of-range values fall back to the bare number so malformed rows never
    crash rendering.
    """
    try:
        return Priority(priority).label
    except ValueError:
        return str(priority)


def _parse_priority_name(value: object) -> object:
    """Convert a priority name to its stored int on the write seam.

    Only strings are converted; other values pass through so pydantic's normal
    ``ge``/``le`` and type errors still fire.
    """
    return int(Priority.parse(value)) if isinstance(value, str) else value


class TaskBase(SQLModel):
    """Base fields for a task."""

    content: str = Field(index=True, min_length=1, max_length=255)
    priority: int = Field(default=1, ge=1, le=3, description="Priority from 1 to 3")
    category: str = Field(
        default="general",
        index=True,
        min_length=1,
        max_length=255,
        description="Free-text category label; lowercased and trimmed on write.",
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

    @field_validator("priority", mode="before")
    @classmethod
    def _parse_priority(cls, value: object) -> object:
        """Accept a priority name (e.g. ``"high"``) as well as its int."""
        return _parse_priority_name(value)


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

    @field_validator("priority", mode="before")
    @classmethod
    def _parse_priority(cls, value: object) -> object:
        """Accept a priority name (e.g. ``"high"``) as well as its int."""
        return _parse_priority_name(value)


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
