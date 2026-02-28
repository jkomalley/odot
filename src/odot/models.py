"""Models for odot."""

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class TaskBase(SQLModel):
    """Base fields for a task."""

    content: str = Field(index=True, min_length=1, max_length=255)
    priority: int = Field(default=1, ge=1, le=3, description="Priority from 1 to 3")
    category: str = Field(default="general", index=True)


class TaskCreate(TaskBase):
    """Model used when creating a task. Inherits all fields from TaskBase."""

    pass


class TaskUpdate(SQLModel):
    """Model for updating a task. All fields are optional."""

    content: str | None = Field(default=None, min_length=1, max_length=255)
    priority: int | None = Field(
        default=None, ge=1, le=3, description="Priority from 1 to 3"
    )
    category: str | None = Field(default=None)
    is_done: bool | None = Field(default=None)


class Task(TaskBase, table=True):
    """The core Task model.

    This defines the 'tasks' table in SQLite.
    """

    id: int | None = Field(default=None, primary_key=True)
    is_done: bool = Field(default=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
