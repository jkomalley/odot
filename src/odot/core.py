"""Core library logic (CRUD operations)."""

from sqlmodel import Session, select

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


def list_tasks(db: Session, is_done: bool | None = None) -> list[Task]:
    """Retrieve tasks with optional filtering.

    Args:
        db: SQLModel Session instance.
        is_done: Filters tasks precisely if set; otherwise returns all tasks.

    Returns:
        A list of matching Task schemas.
    """
    statement = select(Task)
    if is_done is not None:
        statement = statement.where(Task.is_done == is_done)
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
