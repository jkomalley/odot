"""Core library logic (CRUD operations)."""

import json
import sys
from datetime import UTC, datetime
from html import escape
from itertools import groupby
from pathlib import Path
from typing import TextIO

from sqlmodel import Session, col, delete, select

from odot.models import Task, TaskCreate, TaskUpdate

#: Fields accepted by `list_tasks`'s `sort_by` parameter (case-insensitive).
VALID_SORT_FIELDS = ("priority", "date", "category", "status")


def add_task(db: Session, task_data: TaskCreate) -> Task:
    """Add a new task to the database.

    Args:
        db: SQLModel Session instance.
        task_data: Validated properties used for creating a new Task.

    Returns:
        The created Task record.
    """
    task = Task(**task_data.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: int) -> Task | None:
    """Retrieve a single task by its id.

    Args:
        db: SQLModel Session instance.
        task_id: ID of the task to locate.

    Returns:
        The matched Task, or None if no record matches.
    """
    return db.get(Task, task_id)


def list_tasks(
    db: Session,
    is_done: bool | None = None,
    category: str | None = None,
    sort_by: str | None = None,
    reverse: bool = False,
) -> list[Task]:
    """Retrieve tasks with optional filtering and sorting.

    Args:
        db: SQLModel Session instance.
        is_done: Filter by completion status if set; otherwise returns all tasks.
        category: Filter by category if set; otherwise returns all tasks.
        sort_by: Field to sort by, one of `VALID_SORT_FIELDS`
            ('priority', 'date', 'category', 'status'). Case-insensitive.
        reverse: If True, sort descending.

    Returns:
        A list of matching Task schemas.

    Raises:
        ValueError: If `sort_by` is set but is not one of `VALID_SORT_FIELDS`.
    """
    statement = select(Task)

    if is_done is not None:
        statement = statement.where(col(Task.is_done) == is_done)
    if category is not None:
        # Filters are trimmed and lowercased to match normalized storage (#107).
        statement = statement.where(col(Task.category) == category.strip().lower())

    if sort_by:
        normalized = sort_by.lower()
        if normalized not in VALID_SORT_FIELDS:
            msg = (
                f"Invalid sort field: {sort_by!r}. Must be one of {VALID_SORT_FIELDS}."
            )
            raise ValueError(msg)

        field_map = {
            "priority": Task.priority,
            "date": Task.created_at,
            "category": Task.category,
            "status": Task.is_done,
        }

        target_field = field_map[normalized]
        ordering = col(target_field).desc() if reverse else col(target_field).asc()
        statement = statement.order_by(ordering)

    return list(db.exec(statement).all())


def search_tasks(db: Session, phrase: str) -> list[Task]:
    """Search tasks by content phrase.

    Matching is explicitly case-insensitive: both the column and the search
    phrase are lowered via SQL `lower()` before comparison, rather than
    relying on SQLite's default `LIKE` case-folding (which is ASCII-only and
    an implementation detail we don't want to depend on implicitly).

    Args:
        db: SQLModel Session instance.
        phrase: The substring to search for (case-insensitive).

    Returns:
        A list of matching Task schemas.
    """
    statement = select(Task).where(col(Task.content).icontains(phrase))
    return list(db.exec(statement).all())


def update_task(db: Session, task_id: int, data: TaskUpdate) -> Task | None:
    """Update properties of an existing task conditionally.

    Args:
        db: SQLModel Session instance.
        task_id: ID of the task to update.
        data: Validation model containing explicit modification keys.

    Returns:
        The updated Task, or None if no record matches.
    """
    db_task = db.get(Task, task_id)
    if not db_task:
        return None

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return db_task

    db_task.sqlmodel_update(update_data)
    db_task.updated_at = datetime.now(UTC)

    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def delete_task(db: Session, task_id: int) -> bool:
    """Remove a task record entirely.

    Args:
        db: SQLModel Session instance.
        task_id: ID of the task to delete.

    Returns:
        True if the task was found and deleted, False otherwise.
    """
    db_task = db.get(Task, task_id)
    if not db_task:
        return False

    db.delete(db_task)
    db.commit()
    return True


def delete_completed_tasks(db: Session) -> int:
    """Delete all tasks marked as done from the database.

    Args:
        db: SQLModel Session instance.

    Returns:
        The total number of deleted Task records.
    """
    statement = delete(Task).where(col(Task.is_done))
    result = db.exec(statement)
    db.commit()
    return result.rowcount


def delete_all_tasks(db: Session) -> int:
    """Delete all tasks from the database.

    Args:
        db: SQLModel Session instance.

    Returns:
        The total number of deleted Task records.
    """
    statement = delete(Task)
    result = db.exec(statement)
    db.commit()
    return result.rowcount


def export_tasks(
    db: Session,
    path: Path | str | None = None,
    is_done: bool | None = None,
    category: str | None = None,
    pretty: bool = False,
    output: TextIO | None = None,
) -> int:
    """Export tasks to a JSON file, or to a stream when no path is given.

    Args:
        db: SQLModel Session instance.
        path: File path to save the JSON output. If None, JSON is written to
            `output` instead.
        is_done: Optional filter by completion status.
        category: Optional filter by category.
        pretty: Whether to format the JSON string with indentation.
        output: Stream to write JSON to when `path` is None. Defaults to
            `sys.stdout`. Ignored if `path` is provided.

    Returns:
        The total number of exported records.
    """
    tasks = list_tasks(db=db, is_done=is_done, category=category)
    export_data = [task.model_dump(mode="json") for task in tasks]
    indent = 2 if pretty else None

    if path is None:
        stream = output or sys.stdout
        json.dump(export_data, stream, indent=indent)
        # Match the old print() behavior so shell prompts land on a new line.
        stream.write("\n")
    else:
        # File output deliberately has no trailing newline (unchanged behavior).
        file_path = Path(path)
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=indent)

    return len(tasks)


def import_tasks(db: Session, path: Path | str, clear: bool = False) -> int:
    """Import tasks from a JSON file.

    Args:
        db: SQLModel Session instance.
        path: File path mapping to the JSON input.
        clear: Whether to purge existing tasks before importing.

    Returns:
        The total number of imported records.
    """
    if clear:
        delete_all_tasks(db=db)

    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as f:
        import_data = json.load(f)

    count = 0
    for item in import_data:
        task_data = TaskCreate(
            content=item["content"],
            priority=item.get("priority", 1),
            category=item.get("category", "general"),
        )
        task = add_task(db=db, task_data=task_data)

        # Manually apply completion status if previously true
        if item.get("is_done") and task.id is not None:
            update_task(db=db, task_id=task.id, data=TaskUpdate(is_done=True))

        count += 1

    return count


def generate_markdown_report(tasks: list[Task]) -> str:
    """Generate a Markdown report of tasks.

    Args:
        tasks: List of Task objects.

    Returns:
        A Markdown formatted string representing the tasks.
    """
    lines = [
        "# Odot Task Report",
        # Report timestamps are naive local time by design for display.
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",  # noqa: DTZ005
        "",
    ]

    if not tasks:
        lines.append("No tasks found.")
        return "\n".join(lines)

    # Group by category (requires sorting by category first)
    sorted_tasks = sorted(tasks, key=lambda t: t.category)
    for category, category_tasks in groupby(sorted_tasks, key=lambda t: t.category):
        lines.append(f"## {category}")
        for task in category_tasks:
            checkbox = "[x]" if task.is_done else "[ ]"
            lines.append(f"- {checkbox} {task.content} (Priority: {task.priority})")
        lines.append("")

    return "\n".join(lines)


def generate_html_report(tasks: list[Task]) -> str:
    """Generate an HTML report of tasks.

    Args:
        tasks: List of Task objects.

    Returns:
        An HTML formatted string representing the tasks.
    """
    css = """
    body {
        font-family: system-ui, -apple-system, sans-serif;
        max-width: 800px; margin: 0 auto; padding: 20px;
        line-height: 1.6; color: #333;
    }
    h1 { border-bottom: 2px solid #eaeaea; padding-bottom: 10px; }
    h2 { color: #555; margin-top: 30px; }
    .task-list { list-style-type: none; padding-left: 0; }
    .task-item {
        padding: 8px 0; border-bottom: 1px solid #f0f0f0;
        display: flex; align-items: center;
    }
    .task-item:last-child { border-bottom: none; }
    .checkbox {
        margin-right: 12px; font-weight: bold;
        width: 24px; text-align: center;
    }
    .done .checkbox { color: #2ea043; }
    .pending .checkbox { color: #d9d9d9; }
    .content { flex-grow: 1; }
    .done .content { text-decoration: line-through; color: #888; }
    .priority {
        font-size: 0.85em; background: #f0f4f8;
        padding: 2px 6px; border-radius: 4px; color: #586069;
    }
    .meta { font-size: 0.9em; color: #666; font-style: italic; }
    """

    html = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "    <meta charset='UTF-8'>",
        "    <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        "    <title>Odot Task Report</title>",
        f"    <style>{css}</style>",
        "</head>",
        "<body>",
        "    <h1>Odot Task Report</h1>",
        # Report timestamps are naive local time by design for display.
        f"    <p class='meta'>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",  # noqa: DTZ005, E501
    ]

    if not tasks:
        html.append("    <p>No tasks found.</p>")
    else:
        sorted_tasks = sorted(tasks, key=lambda t: t.category)
        for category, category_tasks in groupby(sorted_tasks, key=lambda t: t.category):
            html.append(f"    <h2>{escape(category)}</h2>")
            html.append("    <ul class='task-list'>")
            for task in category_tasks:
                status_class = "done" if task.is_done else "pending"
                checkbox = "✓" if task.is_done else "○"
                html.append(f"        <li class='task-item {status_class}'>")
                html.append(f"            <span class='checkbox'>{checkbox}</span>")
                html.append(
                    f"            <span class='content'>{escape(task.content)}</span>"
                )
                html.append(
                    f"            <span class='priority'>Priority: {task.priority}</span>"  # noqa: E501
                )
                html.append("        </li>")
            html.append("    </ul>")

    html.extend(["</body>", "</html>"])

    return "\n".join(html)
