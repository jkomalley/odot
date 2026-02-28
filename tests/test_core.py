"""Unit tests for core logic CRUD operations."""

from odot import core
from odot.models import TaskCreate, TaskUpdate


def test_add_task(session):
    """Test generating a task successfully."""
    task_data = TaskCreate(content="Clean the kitchen", priority=2)
    task = core.add_task(db=session, task_data=task_data)

    assert task.id is not None
    assert task.content == "Clean the kitchen"
    assert task.priority == 2
    assert task.is_done is False


def test_get_task(session):
    """Test parsing an inserted task and validating None logic for missing ID targets."""
    # Add a task to fetch later
    task_data = TaskCreate(content="Dummy task")
    inserted = core.add_task(db=session, task_data=task_data)

    assert inserted.id is not None
    # Retrieve it
    fetched = core.get_task(db=session, task_id=inserted.id)
    assert fetched is not None
    assert fetched.id == inserted.id
    assert fetched.content == "Dummy task"

    # Check out of bounds requests evaluating None
    missing = core.get_task(db=session, task_id=999)
    assert missing is None


def test_list_tasks(session):
    """Test standard and conditional retrieval logic mappings."""
    # Seed 3 tasks
    core.add_task(db=session, task_data=TaskCreate(content="Task 1"))
    t2 = core.add_task(db=session, task_data=TaskCreate(content="Task 2"))
    core.add_task(db=session, task_data=TaskCreate(content="Task 3"))

    assert t2.id is not None
    # Mark task 2 explicitly as 'done' for filters
    core.update_task(db=session, task_id=t2.id, data=TaskUpdate(is_done=True))

    # Test mapping all
    all_tasks = core.list_tasks(db=session)
    assert len(all_tasks) == 3

    # Test filtering mapping 'not done'
    pending_tasks = core.list_tasks(db=session, is_done=False)
    assert len(pending_tasks) == 2
    assert all(not t.is_done for t in pending_tasks)

    # Test conditional filtering mapping 'done'
    completed_tasks = core.list_tasks(db=session, is_done=True)
    assert len(completed_tasks) == 1
    assert completed_tasks[0].id == t2.id


def test_update_task(session):
    """Test conditional modification tracking logic excluding unmodified properties."""
    task = core.add_task(
        db=session, task_data=TaskCreate(content="Old Task", priority=1)
    )

    assert task.id is not None
    # Execute partial update wrapping just Priority
    updated = core.update_task(db=session, task_id=task.id, data=TaskUpdate(priority=3))
    assert updated is not None
    assert updated.id == task.id
    assert (
        updated.content == "Old Task"
    )  # Stays evaluating explicitly old contents cleanly
    assert updated.priority == 3

    # Check targeting a missing ID evaluation tracking safely
    missing = core.update_task(
        db=session, task_id=999, data=TaskUpdate(content="Missing")
    )
    assert missing is None


def test_delete_task(session):
    """Test dropping records strictly and preventing duplicated exception checks."""
    task = core.add_task(db=session, task_data=TaskCreate(content="Delete me"))
    target_id = task.id

    assert target_id is not None
    # Native evaluation resolving correctly
    success = core.delete_task(db=session, task_id=target_id)
    assert success is True

    # Validation against execution preventing stale read
    verify = core.get_task(db=session, task_id=target_id)
    assert verify is None

    # Double deletion evaluation triggering exception loop bounds mappings strictly correctly to False
    redundant = core.delete_task(db=session, task_id=target_id)
    assert redundant is False
