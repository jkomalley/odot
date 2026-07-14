"""Presentation helpers shared by CLI commands.

Kept separate from `cli.py` so table rendering, time formatting, and text
highlighting can be unit tested as pure functions without going through
Typer's `CliRunner`.
"""

import re
from datetime import datetime, timedelta

from rich.table import Table
from rich.text import Text

from odot.models import Task

#: Rich markup for each priority level, paired with a short text label so the
#: meaning survives even without color (e.g. piped output, colorblind users).
_PRIORITY_DISPLAY = {
    1: "[dim]● Low[/dim]",
    2: "[yellow]●● Med[/yellow]",
    3: "[bold red]●●● High[/bold red]",
}


def priority_display(priority: int) -> str:
    """Render a task priority as a colored dot indicator with a text label.

    Args:
        priority: Priority value (expected 1-3, but any int falls back to
            its plain string form so malformed data never crashes rendering).

    Returns:
        Rich markup string for the priority, or the bare number if it falls
        outside the known 1-3 range.
    """
    return _PRIORITY_DISPLAY.get(priority, str(priority))


def highlight_match(content: str, phrase: str) -> Text:
    """Highlight every case-insensitive occurrence of `phrase` within `content`.

    Uses the `rich.text.Text` API rather than f-string markup injection so
    that content containing literal `[...]` sequences (which would otherwise
    be interpreted as rich markup) renders as plain text everywhere except
    the highlighted span.

    Args:
        content: The full task content to render.
        phrase: The search phrase to highlight. If empty, no highlighting
            is applied.

    Returns:
        A `Text` object with matching spans styled `bold yellow`.
    """
    text = Text(content)
    if not phrase:
        return text

    for match in re.finditer(re.escape(phrase), content, re.IGNORECASE):
        text.stylize("bold yellow", match.start(), match.end())
    return text


def render_task_table(
    tasks: list[Task], *, title: str, highlight: str | None = None
) -> Table:
    """Build a Rich table for a list of tasks.

    Shared by `list` and `search` so both commands render identical columns
    and styling; `search` additionally highlights the matched phrase.

    Args:
        tasks: Tasks to render, one per row.
        title: Table title.
        highlight: Optional phrase to highlight within each row's content
            (used by `search`; `list` omits it).

    Returns:
        A populated Rich `Table` ready to print.
    """
    table = Table(title=title)
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Status", style="green")
    table.add_column("Priority", justify="right")
    table.add_column("Category", style="blue")
    table.add_column("Content")

    for task in tasks:
        status_str = "[green]✓[/]" if task.is_done else "[yellow]○[/]"
        content: str | Text = (
            highlight_match(task.content, highlight) if highlight else task.content
        )
        table.add_row(
            str(task.id),
            status_str,
            priority_display(task.priority),
            task.category,
            content,
        )

    return table


#: Ordered (threshold, formatter) buckets for relative_time, smallest first.
_RELATIVE_TIME_BUCKETS = (
    (timedelta(minutes=1), lambda _delta: "just now"),
    (timedelta(hours=1), lambda delta: f"{int(delta.total_seconds() // 60)}m ago"),
    (timedelta(days=1), lambda delta: f"{int(delta.total_seconds() // 3600)}h ago"),
    (timedelta(days=7), lambda delta: f"{delta.days}d ago"),
)


def relative_time(dt: datetime, now: datetime | None = None) -> str:
    """Format a datetime as a short human-relative string (e.g. "2h ago").

    Args:
        dt: The timestamp to describe, relative to `now`.
        now: Reference point; defaults to `datetime.now()` in `dt`'s
            timezone (or naive local time if `dt` is naive) so callers can
            pass a fixed value for deterministic tests.

    Returns:
        A short relative-time string: "just now", "Xm ago", "Xh ago",
        "Xd ago", or "Xw ago" for anything a week or older.
    """
    if now is None:
        now = datetime.now(dt.tzinfo)

    delta = now - dt
    for threshold, formatter in _RELATIVE_TIME_BUCKETS:
        if delta < threshold:
            return formatter(delta)

    return f"{delta.days // 7}w ago"
