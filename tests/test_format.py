"""Unit tests for presentation helpers in `odot._format`."""

from datetime import UTC, datetime, timedelta
from typing import Any

from rich.text import Text

from odot._format import (
    highlight_match,
    priority_display,
    relative_time,
    render_task_table,
)
from odot.models import Task


def make_task(**overrides: Any) -> Task:
    """Build a Task with sensible defaults, overridable per test."""
    defaults: dict[str, Any] = {
        "id": 1,
        "content": "Sample task",
        "priority": 1,
        "category": "general",
        "is_done": False,
    }
    defaults.update(overrides)
    return Task(**defaults)


class TestPriorityDisplay:
    def test_priority_1_is_low(self):
        assert "Low" in priority_display(1)
        assert "●" in priority_display(1)

    def test_priority_2_is_med(self):
        assert "Med" in priority_display(2)
        assert priority_display(2).count("●") == 2

    def test_priority_3_is_high(self):
        assert "High" in priority_display(3)
        assert priority_display(3).count("●") == 3

    def test_unknown_priority_falls_back_to_number(self):
        # Guards against malformed/legacy data crashing rendering (#54).
        assert priority_display(0) == "0"


class TestHighlightMatch:
    def test_highlights_case_insensitive_match(self):
        text = highlight_match("Buy Groceries for dinner", "groceries")
        assert isinstance(text, Text)
        spans = text.spans
        assert len(spans) == 1
        assert spans[0].style == "bold yellow"
        # The match location covers "Groceries" (case preserved in plain text).
        assert str(text) == "Buy Groceries for dinner"

    def test_highlights_multiple_occurrences(self):
        text = highlight_match("cat cat cat", "cat")
        assert len(text.spans) == 3

    def test_empty_phrase_returns_plain_text_no_highlight(self):
        text = highlight_match("Some content", "")
        assert str(text) == "Some content"
        assert text.spans == []

    def test_content_with_markup_characters_is_not_interpreted(self):
        # Using the Text API (not f-string markup) means literal brackets in
        # content must render literally instead of being swallowed as markup.
        text = highlight_match("Buy [milk] and eggs", "milk")
        assert str(text) == "Buy [milk] and eggs"
        assert len(text.spans) == 1


class TestRenderTaskTable:
    def test_builds_table_with_expected_columns(self):
        tasks = [make_task(id=1, content="Task A")]
        table = render_task_table(tasks, title="My Title")
        assert table.title == "My Title"
        column_headers = [str(c.header) for c in table.columns]
        assert column_headers == ["ID", "Status", "Priority", "Category", "Content"]
        assert table.row_count == 1

    def test_done_task_renders_check_status(self):
        tasks = [make_task(is_done=True)]
        table = render_task_table(tasks, title="T")
        # Row content is stored per-column; status column is index 1.
        status_cell = str(table.columns[1]._cells[0])
        assert "✓" in status_cell

    def test_highlight_wraps_content_in_text_object(self):
        tasks = [make_task(content="Buy groceries")]
        table = render_task_table(tasks, title="Search", highlight="groceries")
        content_cell = table.columns[4]._cells[0]
        assert isinstance(content_cell, Text)

    def test_no_highlight_keeps_plain_string_content(self):
        tasks = [make_task(content="Buy groceries")]
        table = render_task_table(tasks, title="List")
        content_cell = table.columns[4]._cells[0]
        assert content_cell == "Buy groceries"


class TestRelativeTime:
    def test_just_now_under_one_minute(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        dt = now - timedelta(seconds=30)
        assert relative_time(dt, now=now) == "just now"

    def test_minutes_ago(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        dt = now - timedelta(minutes=2)
        assert relative_time(dt, now=now) == "2m ago"

    def test_hours_ago(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        dt = now - timedelta(hours=2)
        assert relative_time(dt, now=now) == "2h ago"

    def test_days_ago(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        dt = now - timedelta(days=3)
        assert relative_time(dt, now=now) == "3d ago"

    def test_weeks_ago(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        dt = now - timedelta(days=14)
        assert relative_time(dt, now=now) == "2w ago"

    def test_boundary_exactly_one_minute_rolls_to_minutes_bucket(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        dt = now - timedelta(minutes=1)
        assert relative_time(dt, now=now) == "1m ago"

    def test_boundary_exactly_one_hour_rolls_to_hours_bucket(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        dt = now - timedelta(hours=1)
        assert relative_time(dt, now=now) == "1h ago"

    def test_boundary_exactly_one_day_rolls_to_days_bucket(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        dt = now - timedelta(days=1)
        assert relative_time(dt, now=now) == "1d ago"

    def test_boundary_exactly_seven_days_rolls_to_weeks_bucket(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        dt = now - timedelta(days=7)
        assert relative_time(dt, now=now) == "1w ago"

    def test_defaults_now_to_current_time_when_omitted(self):
        # No `now` passed: dt is "just now" relative to the real clock.
        dt = datetime.now(UTC)
        assert relative_time(dt) == "just now"
