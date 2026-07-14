"""Unit tests for core logic CRUD operations."""

import io
import json

import pytest

from odot import core
from odot.models import Task, TaskCreate, TaskUpdate


def test_add_task(session):
    """Test generating a task successfully."""
    task_data = TaskCreate(content="Clean the kitchen", priority=2)
    task = core.add_task(db=session, task_data=task_data)

    assert task.id is not None
    assert task.content == "Clean the kitchen"
    assert task.priority == 2
    assert task.is_done is False


def test_get_task(session):
    """Test parsing an inserted task and None handling for a missing ID."""
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
    t1 = core.add_task(
        db=session, task_data=TaskCreate(content="Task 1", category="work")
    )
    t2 = core.add_task(
        db=session, task_data=TaskCreate(content="Task 2", category="personal")
    )
    t3 = core.add_task(
        db=session, task_data=TaskCreate(content="Task 3", category="work")
    )

    assert t1.id is not None
    assert t2.id is not None
    assert t3.id is not None
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

    # Test conditional filtering mapping 'category'
    work_tasks = core.list_tasks(db=session, category="work")
    assert len(work_tasks) == 2
    assert all(t.category == "work" for t in work_tasks)

    # Test combined filtering (category + is_done)
    pending_work_tasks = core.list_tasks(db=session, is_done=False, category="work")
    assert len(pending_work_tasks) == 2

    _ = core.update_task(
        db=session, task_id=t1.id, data=TaskUpdate(is_done=True)
    )  # ID 1: Priority 1, Done
    _ = core.update_task(
        db=session, task_id=t3.id, data=TaskUpdate(priority=3)
    )  # ID 3: Priority 3, Pending

    sort_priority_asc = core.list_tasks(db=session, sort_by="priority")
    assert sort_priority_asc[0].priority == 1
    assert sort_priority_asc[1].priority == 1
    assert sort_priority_asc[-1].priority == 3

    sort_priority_desc = core.list_tasks(db=session, sort_by="priority", reverse=True)
    assert sort_priority_desc[0].priority == 3
    assert sort_priority_desc[-1].priority == 1

    # Status Sort
    sort_status = core.list_tasks(db=session, sort_by="status")
    assert not sort_status[0].is_done
    assert sort_status[-1].is_done

    sort_status_desc = core.list_tasks(db=session, sort_by="status", reverse=True)
    assert sort_status_desc[0].is_done
    assert not sort_status_desc[-1].is_done

    # Date Sort
    sort_date = core.list_tasks(db=session, sort_by="date")
    assert sort_date[0].id == t1.id
    assert sort_date[-1].id == t3.id

    sort_date_desc = core.list_tasks(db=session, sort_by="date", reverse=True)
    assert sort_date_desc[0].id == t3.id
    assert sort_date_desc[-1].id == t1.id

    # Category Sort
    sort_category = core.list_tasks(db=session, sort_by="category")
    assert sort_category[0].category == "personal"
    assert sort_category[-1].category == "work"


def test_list_tasks_invalid_sort_raises(session):
    """Test that an invalid sort_by value raises ValueError (see #47, #50)."""
    core.add_task(db=session, task_data=TaskCreate(content="A", priority=2))
    core.add_task(db=session, task_data=TaskCreate(content="B", priority=1))

    with pytest.raises(ValueError, match="Invalid sort field"):
        core.list_tasks(db=session, sort_by="nonexistent")


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
    assert updated.content == "Old Task"
    assert updated.priority == 3
    assert updated.updated_at is not None
    assert updated.updated_at > updated.created_at

    missing = core.update_task(
        db=session, task_id=999, data=TaskUpdate(content="Missing")
    )
    assert missing is None

    updated_noop = core.update_task(db=session, task_id=task.id, data=TaskUpdate())
    assert updated_noop is not None
    assert updated_noop.content == "Old Task"
    assert updated_noop.updated_at == updated.updated_at


def test_delete_task(session):
    """Test dropping records strictly and preventing duplicated exception checks."""
    task = core.add_task(db=session, task_data=TaskCreate(content="Delete me"))
    target_id = task.id

    assert target_id is not None
    success = core.delete_task(db=session, task_id=target_id)
    assert success is True

    redundant = core.delete_task(db=session, task_id=target_id)
    assert redundant is False


def test_search_tasks(session):
    """Test searching tasks by description phrase."""
    core.add_task(db=session, task_data=TaskCreate(content="Clean the kitchen"))
    core.add_task(db=session, task_data=TaskCreate(content="Buy groceries"))
    core.add_task(db=session, task_data=TaskCreate(content="Quarterly report draft"))

    # Exact match
    results = core.search_tasks(db=session, phrase="groceries")
    assert len(results) == 1
    assert results[0].content == "Buy groceries"

    # Case-insensitive partial match
    results = core.search_tasks(db=session, phrase="QUARTERLY")
    assert len(results) == 1
    assert results[0].content == "Quarterly report draft"

    # Match multiple (all contain 'e')
    results = core.search_tasks(db=session, phrase="e")
    assert len(results) == 3

    # Match none
    results = core.search_tasks(db=session, phrase="notfound")
    assert len(results) == 0


def test_search_tasks_mixed_case(session):
    """Test that mixed-case phrases match regardless of stored casing."""
    core.add_task(db=session, task_data=TaskCreate(content="Review PR Feedback"))

    # Mixed-case phrase against mixed-case content
    results = core.search_tasks(db=session, phrase="pR fEEdback")
    assert len(results) == 1
    assert results[0].content == "Review PR Feedback"

    # All-lowercase phrase
    results = core.search_tasks(db=session, phrase="review")
    assert len(results) == 1

    # All-uppercase phrase
    results = core.search_tasks(db=session, phrase="REVIEW")
    assert len(results) == 1


def test_delete_completed_tasks(session):
    """Test dropping only records marked as done."""
    t1 = core.add_task(db=session, task_data=TaskCreate(content="Dummy task 1"))
    t2 = core.add_task(db=session, task_data=TaskCreate(content="Dummy task 2"))
    t3 = core.add_task(db=session, task_data=TaskCreate(content="Dummy task 3"))

    assert t1.id is not None
    assert t3.id is not None

    # Mark task 1 and 3 as done
    core.update_task(db=session, task_id=t1.id, data=TaskUpdate(is_done=True))
    core.update_task(db=session, task_id=t3.id, data=TaskUpdate(is_done=True))

    assert len(core.list_tasks(db=session)) == 3

    count = core.delete_completed_tasks(db=session)
    assert count == 2

    # Verify only task 2 remains
    remaining = core.list_tasks(db=session)
    assert len(remaining) == 1
    assert remaining[0].id == t2.id

    # Verify repeated calls return 0
    count_again = core.delete_completed_tasks(db=session)
    assert count_again == 0


def test_delete_all_tasks(session):
    """Test dropping all records entirely regardless of status."""
    core.add_task(db=session, task_data=TaskCreate(content="Dummy task 1"))
    core.add_task(db=session, task_data=TaskCreate(content="Dummy task 2"))
    core.add_task(db=session, task_data=TaskCreate(content="Dummy task 3"))

    assert len(core.list_tasks(db=session)) == 3

    count = core.delete_all_tasks(db=session)
    assert count == 3

    assert len(core.list_tasks(db=session)) == 0

    # Ensure empty DB drops 0 safely
    count_again = core.delete_all_tasks(db=session)
    assert count_again == 0


def test_export_tasks(session, tmp_path):
    """Test JSON exporting with filtering."""
    core.add_task(
        db=session, task_data=TaskCreate(content="Dummy task 1", category="work")
    )
    t2 = core.add_task(
        db=session, task_data=TaskCreate(content="Dummy task 2", category="personal")
    )
    core.add_task(
        db=session, task_data=TaskCreate(content="Dummy task 3", category="work")
    )

    # Mark task 2 explicitly as 'done' for filters
    assert t2.id is not None
    core.update_task(db=session, task_id=t2.id, data=TaskUpdate(is_done=True))

    export_file = tmp_path / "export.json"

    # Export all
    count = core.export_tasks(db=session, path=export_file)
    assert count == 3
    with export_file.open() as f:
        data = json.load(f)
        assert len(data) == 3

    count = core.export_tasks(
        db=session, path=export_file, category="work", pretty=True
    )
    assert count == 2
    with export_file.open() as f:
        data = json.load(f)
        assert len(data) == 2
        assert "Dummy task 1" in str(data)
        assert "Dummy task 3" in str(data)

    # Injectable output stream (no path): defaults to sys.stdout when omitted.
    captured_output = io.StringIO()
    count = core.export_tasks(db=session, pretty=False, output=captured_output)
    assert count == 3
    data = json.loads(captured_output.getvalue())
    assert len(data) == 3


def test_export_tasks_defaults_to_stdout(session, monkeypatch):
    """Test that export_tasks writes to sys.stdout when output is not given."""
    core.add_task(db=session, task_data=TaskCreate(content="Dummy task"))

    captured_output = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured_output)

    count = core.export_tasks(db=session)
    assert count == 1
    data = json.loads(captured_output.getvalue())
    assert len(data) == 1


def test_import_tasks(session, tmp_path):
    """Test importing tasks from a JSON file."""
    import_file = tmp_path / "import.json"

    # Write some dummy payload explicitly
    payload = [
        {"content": "Import 1", "priority": 3, "category": "work", "is_done": False},
        {"content": "Import 2", "priority": 1, "category": "personal", "is_done": True},
    ]
    with import_file.open("w") as f:
        json.dump(payload, f)

    core.add_task(db=session, task_data=TaskCreate(content="Pre payload task"))

    count = core.import_tasks(db=session, path=str(import_file))
    assert count == 2

    tasks = core.list_tasks(db=session)
    assert len(tasks) == 3
    assert any(t.content == "Import 1" and t.priority == 3 for t in tasks)
    assert any(t.content == "Import 2" and t.is_done is True for t in tasks)

    count = core.import_tasks(db=session, path=str(import_file), clear=True)
    assert count == 2
    tasks_after_clear = core.list_tasks(db=session)
    assert len(tasks_after_clear) == 2


def test_import_tasks_missing_content(session, tmp_path):
    """Test that importing JSON with a missing content key raises KeyError."""
    bad_file = tmp_path / "bad_import.json"
    payload = [{"priority": 2, "category": "work"}]  # missing content
    bad_file.write_text(json.dumps(payload))

    with pytest.raises(KeyError):
        core.import_tasks(db=session, path=str(bad_file))

    # Nothing should have been committed before the failure.
    assert core.list_tasks(db=session) == []


def test_import_tasks_empty_array(session, tmp_path):
    """Test that importing an empty JSON array adds no tasks."""
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("[]")

    count = core.import_tasks(db=session, path=str(empty_file))
    assert count == 0
    assert core.list_tasks(db=session) == []


def test_import_tasks_ignores_unknown_fields(session, tmp_path):
    """Test that extra/unexpected JSON fields are silently ignored."""
    extra_file = tmp_path / "extra_fields.json"
    payload = [
        {
            "content": "Task with extras",
            "priority": 2,
            "category": "work",
            "unexpected_field": "should be ignored",
            "another_bogus_key": 123,
        }
    ]
    extra_file.write_text(json.dumps(payload))

    count = core.import_tasks(db=session, path=str(extra_file))
    assert count == 1

    tasks = core.list_tasks(db=session)
    assert len(tasks) == 1
    assert tasks[0].content == "Task with extras"
    assert tasks[0].priority == 2
    assert not hasattr(tasks[0], "unexpected_field")


def test_generate_markdown_report():
    """Test generating a markdown formatted report string."""
    tasks = [
        Task(content="Work Task", priority=3, category="work", is_done=False),
        Task(content="Personal Task", priority=1, category="personal", is_done=True),
    ]
    report = core.generate_markdown_report(tasks)

    assert "# Odot Task Report" in report
    assert "## Personal" in report
    assert "- [x] Personal Task (Priority: 1)" in report
    assert "## Work" in report
    assert "- [ ] Work Task (Priority: 3)" in report

    empty_report = core.generate_markdown_report([])
    assert "No tasks found." in empty_report


def test_generate_html_report():
    """Test generating an HTML formatted report string."""
    tasks = [
        Task(content="Work Task", priority=3, category="work", is_done=False),
        Task(content="Personal Task", priority=1, category="personal", is_done=True),
    ]
    report = core.generate_html_report(tasks)

    assert "<!DOCTYPE html>" in report
    assert "<h1>Odot Task Report</h1>" in report
    assert "<h2>Personal</h2>" in report
    assert "<h2>Work</h2>" in report
    assert "Personal Task" in report
    assert "Work Task" in report
    assert "class='task-item done'" in report
    assert "class='task-item pending'" in report

    empty_report = core.generate_html_report([])
    assert "<p>No tasks found.</p>" in empty_report


def test_generate_html_report_escapes_user_content():
    """HTML special characters in user content must be escaped."""
    tasks = [
        Task(
            content='Review <head> section & fix "quotes"',
            priority=1,
            category="<script>alert('xss')</script>",
            is_done=False,
        )
    ]
    report = core.generate_html_report(tasks)

    assert "<script>" not in report
    assert "&lt;head&gt;" in report
    assert "&amp;" in report
    assert "&quot;quotes&quot;" in report
    assert "&lt;Script&gt;" in report
