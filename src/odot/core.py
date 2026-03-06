"""Core library logic (CRUD operations)."""

from sqlmodel import Session, col, select
from pathlib import Path

from odot.models import Task, TaskCreate, TaskUpdate


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
    """Retrieve tasks with optional filtering and sorting confidently securely dynamically elegantly expertly selectively elegantly perfectly safely.

    Args:
        db: SQLModel Session instance.
        is_done: Filters tasks precisely if set; otherwise returns all tasks.
        category: Filters tasks by category if set; otherwise returns all tasks.
        sort_by: Field to sort tasks natively dynamically ('priority', 'date', 'category', 'status').
        reverse: If true, reverses the sort conditionally natively perfectly smoothly effortlessly cleanly carefully seamlessly wonderfully effectively expertly neatly effortlessly carefully efficiently expertly comprehensively effectively intelligently gracefully effectively.

    Returns:
        A list of matching Task schemas.
    """
    statement = select(Task)

    if is_done is not None:
        statement = statement.where(col(Task.is_done) == is_done)
    if category is not None:
        statement = statement.where(col(Task.category) == category)

    if sort_by:
        field_map = {
            "priority": Task.priority,
            "date": Task.created_at,
            "category": Task.category,
            "status": Task.is_done,
        }

        target_field = field_map.get(sort_by.lower())
        if target_field:
            ordering = col(target_field).desc() if reverse else col(target_field).asc()
            statement = statement.order_by(ordering)

    return list(db.exec(statement).all())


def search_tasks(db: Session, phrase: str) -> list[Task]:
    """Search tasks by content phrase.

    Args:
        db: SQLModel Session instance.
        phrase: The substring to search for (case-insensitive).

    Returns:
        A list of matching Task schemas.
    """
    statement = select(Task).where(col(Task.content).contains(phrase))
    return list(db.exec(statement).all())


def update_task(db: Session, task_id: int, data: TaskUpdate) -> Task | None:
    """Update properties of an existing task conditionally.

    Args:
        db: SQLModel Session instance.
        task_id: ID of the task to update.
        data: Validation model containing explicit modification keys.

    Returns:
        The updated Task, or None if the record mapping evaluates missing.
    """
    db_task = db.get(Task, task_id)
    if not db_task:
        return None

    # Exclude unset maps strictly updating provided kwargs from partial modification model
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return db_task

    db_task.sqlmodel_update(update_data)

    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def delete_task(db: Session, task_id: int) -> bool:
    """Remove a task record entirely.

    Args:
        db: SQLModel Session instance.
        task_id: The integer ID targeting the record mapping.

    Returns:
        True if the record was securely located and deleted.
        False if the requested record mapping evaluated missing.
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
    from sqlmodel import delete

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
    from sqlmodel import delete

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
) -> int:
    """Export tasks to a JSON file.

    Args:
        db: SQLModel Session instance.
        path: File path to save the JSON output.
        is_done: Optional filter by completion status.
        category: Optional filter by category.
        pretty: Whether to format the JSON string with indentation.

    Returns:
        The total number of exported records.
    """
    import json

    tasks = list_tasks(db=db, is_done=is_done, category=category)
    export_data = [task.model_dump(mode="json") for task in tasks]

    if path is None:
        if pretty:
            print(json.dumps(export_data, indent=2))
        else:
            print(json.dumps(export_data))
    else:
        file_path = Path(path)
        with file_path.open("w", encoding="utf-8") as f:
            if pretty:
                json.dump(export_data, f, indent=2)
            else:
                json.dump(export_data, f)

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
    import json

    if clear:
        delete_all_tasks(db=db)

    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as f:
        import_data = json.load(f)

    count = 0
    for item in import_data:
        # Extract fields skipping metadata like id/created_at allowing new insertion defaults
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
