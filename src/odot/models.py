"""Models for odot."""

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Task(SQLModel, table=True):
    """The core Task model.

    This defines the 'tasks' table in SQLite and validates CLI input.
    """

    id: int | None = Field(default=None, primary_key=True)

    # The actual task text
    content: str = Field(index=True, min_length=1, max_length=255)

    # Priority: 1 (Low), 2 (Medium), 3 (High)
    priority: int = Field(default=1, ge=1, le=3, description="Priority from 1 to 3")

    # Status
    is_done: bool = Field(default=False)

    # Metadata
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Optional category/tag (e.g., 'work', 'gym')
    category: str | None = Field(default="general", index=True)
