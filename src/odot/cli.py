"""Typer CLI application."""

import importlib.metadata
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import questionary
import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from sqlmodel import Session

from odot import core, database
from odot._format import relative_time, render_task_table
from odot.models import Task, TaskCreate, TaskUpdate

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass
class AppContext:
    """Per-invocation state stored on `ctx.obj`.

    Holds the shared database session plus whether the global (or per-command)
    `--json` flag was set, so every command can consult one place to decide
    between Rich output and machine-readable JSON.
    """

    session: Session
    json_output: bool = False


class SortField(StrEnum):
    """Fields accepted by the --sort option on `list` and `report`.

    Mirrors `core.VALID_SORT_FIELDS`; a test asserts the two stay in sync.
    Using an Enum as the Typer option type moves validation to parse time,
    so an invalid value is rejected by Typer itself (usage error, exit 2)
    instead of by hand-rolled checks inside each command.
    """

    PRIORITY = "priority"
    DATE = "date"
    CATEGORY = "category"
    STATUS = "status"


# invoke_without_command lets `odot` with no subcommand fall through to
# main_callback instead of auto-printing help (see #61); help remains
# reachable via --help since Typer still special-cases that flag.
app = typer.Typer(
    name="odot",
    help="A minimalist CLI task manager.",
    invoke_without_command=True,
)
console = Console()
#: Errors are written here so stdout stays a clean JSON channel under --json.
err_console = Console(stderr=True)

#: Reusable per-command `--json` option. The global flag on the app callback
#: (`odot --json <cmd>`) is the primary form, but the issue's examples also
#: show `odot list --json`, so each command accepts the flag in its own
#: position too; the two are OR-ed together via `json_enabled`.
JsonOption = Annotated[
    bool,
    typer.Option("--json", help="Output machine-readable JSON instead of a table."),
]


def emit_json(data: object) -> None:
    """Print a JSON document to stdout as the sole output of a `--json` command.

    Plain `print(json.dumps(...))` is used rather than `console.print_json` so
    the output is never soft-wrapped or styled: the result is a single valid
    JSON document safe to pipe into `jq` or `python -m json.tool`.

    Args:
        data: Any JSON-serializable value (a list of task dicts, a single task
            dict, or a small summary dict).
    """
    print(json.dumps(data))


def json_enabled(ctx: typer.Context, local: bool) -> bool:
    """Return whether JSON output is active for the current command.

    True if either the global callback flag (`odot --json ...`) or the
    command's own `--json` flag (`odot ... --json`) was given.
    """
    return bool(getattr(ctx.obj, "json_output", False)) or local


def json_error(message: str, *, code: int = 1) -> typer.Exit:
    """Print an error to stderr and return an `Exit` to raise.

    Keeps stdout a clean JSON channel: under --json all diagnostics go to
    stderr. Returned (not raised) so callers keep an explicit `raise`.
    """
    err_console.print(f"[red]{message}[/red]")
    return typer.Exit(code=code)


def require_task_id(
    ctx: typer.Context, task_id: int | None, action: str, *, as_json: bool
) -> int:
    """Resolve a task id, prompting interactively unless JSON mode is active.

    Under --json there is no TTY to prompt on, so a missing id is a usage
    error (exit 2) written to stderr instead of an interactive selection.
    """
    if task_id is not None:
        return task_id
    if as_json:
        raise json_error("A task id is required in --json mode.", code=2)
    return prompt_task_selection(ctx.obj.session, action)


def require_force(force: bool, prompt: str, *, as_json: bool) -> None:
    """Confirm a destructive action, requiring --force in JSON mode.

    Interactive confirmations cannot run under --json (no TTY), so --force is
    mandatory there; without it, a usage error (exit 2) is emitted to stderr.
    """
    if force:
        return
    if as_json:
        raise json_error("--force is required in --json mode.", code=2)
    typer.confirm(prompt, abort=True)


def prompt_task_selection(db: Session, action: str) -> int:
    """Prompt the user to select a task using an interactive TUI list."""
    tasks = core.list_tasks(db=db)
    if not tasks:
        console.print("[yellow]No tasks available.[/yellow]")
        raise typer.Exit

    choices = [
        questionary.Choice(
            title=f"ID {t.id} │ {t.content} [{'✔' if t.is_done else '○'}]", value=t.id
        )
        for t in tasks
    ]

    task_id = questionary.select(f"Select a task to {action}:", choices=choices).ask()

    if task_id is None:
        console.print("[yellow]Operation cancelled.[/yellow]")
        raise typer.Exit

    return task_id


def version_callback(value: bool) -> None:
    """Callback for version printing."""
    if value:
        version = importlib.metadata.version("odot")
        console.print(f"odot version: {version}")
        raise typer.Exit


def print_summary_footer(tasks: list[Task], *, category: str | None = None) -> None:
    """Print a dim counts line beneath a task table (#55).

    The pending/done breakdown already reflects any active --done/--todo
    filter (one side will simply be zero), so only the category needs to be
    echoed explicitly for context.

    Args:
        tasks: The (already filtered) tasks being displayed.
        category: The active --category filter, if any, echoed for context.
    """
    done_count = sum(1 for t in tasks if t.is_done)
    pending_count = len(tasks) - done_count

    category_suffix = f' in "{category}"' if category is not None else ""
    console.print(
        f"[dim]{len(tasks)} tasks{category_suffix} "
        f"({pending_count} pending, {done_count} done)[/dim]"
    )


def print_empty_state(db: Session, *, category: str | None, done: bool | None) -> None:
    """Print a helpful empty-state message for `list` (#58).

    Distinguishes a genuinely empty database (onboarding message) from a
    filter that simply matched nothing (message names the filter and
    reports the true total so the user knows the data is still there). This
    function is only called when the filtered result set is empty, so if the
    unfiltered total is also 0, at least one filter must be active — the
    filtered/onboarding branches are mutually exhaustive by construction.
    """
    total = len(core.list_tasks(db=db))
    if total == 0:
        console.print('No tasks yet. Add one with:  odot add "Your first task"')
        return

    status_word = f"{'completed' if done else 'pending'} " if done is not None else ""
    category_suffix = f' in "{category}"' if category is not None else ""
    console.print(
        f"No {status_word}tasks found{category_suffix}. ({total} total tasks)"
    )


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: Annotated[  # noqa: ARG001  # eager option triggers version_callback
        bool | None,
        typer.Option(
            "--version",
            "-v",
            callback=version_callback,
            is_eager=True,
            help="Show the application's version and exit.",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help=(
                "Output machine-readable JSON. Applies to list/show/add/update/"
                "done/undo/search/count/rm/clean/purge/import; ignored by "
                "export/report/init-db, which produce their own artifacts."
            ),
        ),
    ] = False,
) -> None:
    """A minimalist CLI task manager."""
    if getattr(ctx, "obj", None) is None:
        db_path = database.get_db_path()
        # Auto-init's "Database initialized" notice would corrupt the JSON on
        # stdout, so route it to stderr when JSON output is requested.
        if not db_path.exists():
            database.create_db_and_tables()
            notice = f"[dim]Database initialized at {db_path}[/dim]"
            (err_console if json_output else console).print(notice)
        session = Session(database.get_engine())
        ctx.obj = AppContext(session=session, json_output=json_output)
        ctx.call_on_close(session.close)

    # Bare `odot` (#61): show the task list, the most common intent, rather
    # than help. `--help` is unaffected since Typer intercepts it earlier.
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_tasks, ctx=ctx)


@app.command()
def add(
    ctx: typer.Context,
    content: Annotated[str | None, typer.Argument(help="Task content")] = None,
    priority: Annotated[
        int, typer.Option("-p", "--priority", help="Priority from 1 to 3")
    ] = 1,
    category: Annotated[
        str, typer.Option("-c", "--category", help="Category label")
    ] = "general",
    json_output: JsonOption = False,
) -> None:
    """Add a new task."""
    as_json = json_enabled(ctx, json_output)
    if content is None:
        if as_json:
            raise json_error("Task content is required in --json mode.", code=2)
        content = Prompt.ask("Task content")

    db = ctx.obj.session
    task_data = TaskCreate(content=content, priority=priority, category=category)
    task = core.add_task(db=db, task_data=task_data)
    if as_json:
        emit_json(task.model_dump(mode="json"))
        return
    console.print(f'[green]✅ Added task {task.id}: "{task.content}"[/green]')
    console.print(
        f"[dim]   Priority: {task.priority} │ Category: {task.category} "
        f"│ Created: just now[/dim]"
    )


@app.command()
def show(
    ctx: typer.Context,
    task_id: Annotated[int | None, typer.Argument(help="Task ID to show")] = None,
    json_output: JsonOption = False,
) -> None:
    """Show details for a specific task."""
    as_json = json_enabled(ctx, json_output)
    db = ctx.obj.session
    task_id = require_task_id(ctx, task_id, "show", as_json=as_json)
    task = core.get_task(db=db, task_id=task_id)
    if not task:
        if as_json:
            raise json_error(f"Task {task_id} not found.")
        console.print(f"[red]Task {task_id} not found.[/red]")
        raise typer.Exit(code=1)

    if as_json:
        emit_json(task.model_dump(mode="json"))
        return

    table = Table(title=f"Task {task.id}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Content", task.content)
    table.add_row("Priority", str(task.priority))
    table.add_row("Category", task.category)
    table.add_row("Status", "Done" if task.is_done else "Pending")

    # Relative time (#56) is appended alongside the absolute timestamp so
    # both the precise value and the at-a-glance "how long ago" are visible.
    local_time = task.created_at.astimezone()
    table.add_row(
        "Created At",
        f"{local_time.strftime(DATETIME_FORMAT)} ({relative_time(task.created_at)})",
    )

    if task.updated_at:
        local_updated = task.updated_at.astimezone()
        table.add_row(
            "Updated At",
            f"{local_updated.strftime(DATETIME_FORMAT)} "
            f"({relative_time(task.updated_at)})",
        )

    console.print(table)


@app.command(name="list")
def list_tasks(
    ctx: typer.Context,
    done: Annotated[
        bool | None, typer.Option("-d/-t", "--done/--todo", help="Filter by status")
    ] = None,
    category: Annotated[
        str | None, typer.Option("-c", "--category", help="Filter by category")
    ] = None,
    sort: Annotated[
        SortField | None,
        typer.Option(
            "-s",
            "--sort",
            help="Sort by field: priority, date, category, status",
        ),
    ] = None,
    reverse: Annotated[
        bool,
        typer.Option(
            "-r",
            "--reverse",
            help="Reverse the sort order (descending)",
        ),
    ] = False,
    json_output: JsonOption = False,
) -> None:
    """List tasks, optionally filtered and sorted."""
    as_json = json_enabled(ctx, json_output)
    db = ctx.obj.session

    tasks = core.list_tasks(
        db=db,
        is_done=done,
        category=category,
        sort_by=sort,
        reverse=reverse,
    )

    if as_json:
        emit_json([task.model_dump(mode="json") for task in tasks])
        return

    if not tasks:
        print_empty_state(db, category=category, done=done)
        return

    table = render_task_table(tasks, title="Odot Tasks")
    console.print(table)
    print_summary_footer(tasks, category=category)


@app.command()
def count(
    ctx: typer.Context,
    done: Annotated[
        bool | None, typer.Option("-d/-t", "--done/--todo", help="Filter by status")
    ] = None,
    category: Annotated[
        str | None, typer.Option("-c", "--category", help="Filter by category")
    ] = None,
    json_output: JsonOption = False,
) -> None:
    """Print task counts without rendering a full table (#58)."""
    db = ctx.obj.session
    tasks = core.list_tasks(db=db, is_done=done, category=category)

    if json_enabled(ctx, json_output):
        # Report the full total/pending/done breakdown regardless of the
        # active filter so the JSON shape is stable for scripts; the filter is
        # already reflected in which tasks were counted.
        done_count = sum(1 for t in tasks if t.is_done)
        emit_json(
            {
                "total": len(tasks),
                "pending": len(tasks) - done_count,
                "done": done_count,
            }
        )
        return

    # done/todo filters collapse the line to a single count since the other
    # status is, by definition, excluded; combined with --category it reads
    # naturally as "N completed work tasks", matching the issue's examples.
    if done is not None:
        status_word = "completed" if done else "pending"
        category_prefix = f"{category} " if category else ""
        noun = "task" if len(tasks) == 1 else "tasks"
        console.print(f"{len(tasks)} {status_word} {category_prefix}{noun}")
        return

    done_count = sum(1 for t in tasks if t.is_done)
    pending_count = len(tasks) - done_count
    category_suffix = f' in "{category}"' if category else ""
    console.print(
        f"{len(tasks)} tasks{category_suffix} ({pending_count} pending, "
        f"{done_count} done)"
    )


@app.command()
def search(
    ctx: typer.Context,
    phrase: Annotated[str, typer.Argument(help="Phrase to search for in task content")],
    json_output: JsonOption = False,
) -> None:
    """Search for tasks containing a specific phrase."""
    db = ctx.obj.session
    tasks = core.search_tasks(db=db, phrase=phrase)

    if json_enabled(ctx, json_output):
        emit_json([task.model_dump(mode="json") for task in tasks])
        return

    if not tasks:
        console.print(f"No tasks matching '{phrase}' found.")
        return

    table = render_task_table(tasks, title="Search Results", highlight=phrase)
    console.print(table)


def _prompt_update_fields() -> dict[str, Any] | None:
    """Interactively collect update fields via a questionary checkbox form.

    Split out of `update` to keep that command's branch count under the
    complexity gate; this owns the entire "no flags given" fallback path.

    Returns:
        A kwargs dict suitable for `TaskUpdate(**kwargs)`, which may be
        empty if every individual field prompt was cancelled (still a valid
        no-op update). Returns None only if the initial checkbox itself was
        cancelled/empty, which the caller treats as a hard error.
    """
    choices = questionary.checkbox(
        "Select fields to update:",
        choices=["content", "priority", "category", "done"],
    ).ask()

    if not choices:
        return None

    update_kwargs: dict[str, Any] = {}
    if "content" in choices:
        update_kwargs["content"] = Prompt.ask("New content")
    if "priority" in choices:
        priority_str = questionary.select(
            "New priority:", choices=["1", "2", "3"]
        ).ask()
        if priority_str:
            update_kwargs["priority"] = int(priority_str)
    if "category" in choices:
        update_kwargs["category"] = Prompt.ask("New category")
    if "done" in choices:
        update_kwargs["is_done"] = questionary.confirm("Is the task done?").ask()

    return update_kwargs


def _snapshot(task: Task) -> dict[str, Any]:
    """Copy the fields `update` diffs into a plain dict.

    SQLAlchemy's identity map returns the *same* Python object for repeated
    `get`/`update` calls on the same primary key within a session, so a
    `before = get_task(...)` reference would be silently mutated in place by
    the subsequent `update_task` call. Copying the plain values here is what
    makes the before/after diff in `_print_update_diff` actually work.
    """
    return {
        "content": task.content,
        "priority": task.priority,
        "category": task.category,
        "is_done": task.is_done,
    }


def _print_update_diff(before: dict[str, Any], after: Task) -> None:
    """Print a field-by-field diff line for each value `update` changed (#57)."""
    for field in ("content", "priority", "category"):
        old_value = before[field]
        new_value = getattr(after, field)
        if old_value != new_value:
            console.print(f"[dim]   {field}: {old_value} → {new_value}[/dim]")
    if before["is_done"] != after.is_done:
        old_status = "Done" if before["is_done"] else "Pending"
        new_status = "Done" if after.is_done else "Pending"
        console.print(f"[dim]   status: {old_status} → {new_status}[/dim]")


@app.command()
def update(
    ctx: typer.Context,
    task_id: Annotated[int | None, typer.Argument(help="Task ID to update")] = None,
    content: Annotated[
        str | None, typer.Option("-m", "--content", help="Update task text")
    ] = None,
    priority: Annotated[
        int | None, typer.Option("-p", "--priority", help="Update priority (1-3)")
    ] = None,
    category: Annotated[
        str | None, typer.Option("-c", "--category", help="Update category")
    ] = None,
    done: Annotated[
        bool | None,
        typer.Option("-d/-t", "--done/--todo", help="Update completion status"),
    ] = None,
    json_output: JsonOption = False,
) -> None:
    """Update properties of an existing task."""
    as_json = json_enabled(ctx, json_output)
    db = ctx.obj.session
    task_id = require_task_id(ctx, task_id, "update", as_json=as_json)

    # Collect only the arguments the user explicitly provided on the command line.
    provided_args = {
        "content": content,
        "priority": priority,
        "category": category,
        "is_done": done,
    }
    update_kwargs: dict[str, Any] = {
        k: v for k, v in provided_args.items() if v is not None
    }

    # If no flags are provided, ask interactively via a checkbox form — but
    # never under --json, where at least one update flag is required (exit 2).
    if not update_kwargs:
        if as_json:
            raise json_error(
                "At least one field flag is required in --json mode.", code=2
            )
        prompted = _prompt_update_fields()
        if prompted is None:
            console.print("[yellow]No updates provided.[/yellow]")
            raise typer.Exit(code=1)
        update_kwargs = prompted

    # Look the task up first (rather than only checking update_task's return)
    # so we can both report not-found up front and snapshot the before-state
    # for the diff (#57) — snapshotting the same live update_task result
    # would be a no-op since SQLAlchemy's identity map mutates it in place.
    existing = core.get_task(db=db, task_id=task_id)
    if not existing:
        if as_json:
            raise json_error(f"Task {task_id} not found.")
        console.print(f"[red]Task {task_id} not found.[/red]")
        raise typer.Exit(code=1)
    before = _snapshot(existing)

    update_data = TaskUpdate(**update_kwargs)
    task = core.update_task(db=db, task_id=task_id, data=update_data)
    if not task:  # pragma: no cover - existing was just confirmed present above
        console.print(f"[red]Task {task_id} not found.[/red]")
        raise typer.Exit(code=1)

    if as_json:
        emit_json(task.model_dump(mode="json"))
        return

    console.print(f"[green]✏️  Updated task #{task.id}[/green]")
    _print_update_diff(before, task)


@app.command()
def done(
    ctx: typer.Context,
    task_id: Annotated[
        int | None, typer.Argument(help="Task ID to mark as done")
    ] = None,
    json_output: JsonOption = False,
) -> None:
    """Mark a task as done."""
    as_json = json_enabled(ctx, json_output)
    db = ctx.obj.session
    task_id = require_task_id(ctx, task_id, "mark done", as_json=as_json)
    task = core.update_task(db=db, task_id=task_id, data=TaskUpdate(is_done=True))
    if not task:
        if as_json:
            raise json_error(f"Task {task_id} not found.")
        console.print(f"[red]Task {task_id} not found.[/red]")
        raise typer.Exit(code=1)
    if as_json:
        emit_json(task.model_dump(mode="json"))
        return
    console.print(f'[green]✅ Marked done: "{task.content}" (task #{task.id})[/green]')


@app.command()
def undo(
    ctx: typer.Context,
    task_id: Annotated[int | None, typer.Argument(help="Task ID to re-open")] = None,
    json_output: JsonOption = False,
) -> None:
    """Re-open a completed task."""
    as_json = json_enabled(ctx, json_output)
    db = ctx.obj.session
    task_id = require_task_id(ctx, task_id, "re-open", as_json=as_json)
    task = core.update_task(db=db, task_id=task_id, data=TaskUpdate(is_done=False))
    if not task:
        if as_json:
            raise json_error(f"Task {task_id} not found.")
        console.print(f"[red]Task {task_id} not found.[/red]")
        raise typer.Exit(code=1)
    if as_json:
        emit_json(task.model_dump(mode="json"))
        return
    console.print(f'[green]↩️  Re-opened: "{task.content}" (task #{task.id})[/green]')


@app.command()
def rm(
    ctx: typer.Context,
    task_id: Annotated[int | None, typer.Argument(help="Task ID to remove")] = None,
    force: Annotated[
        bool, typer.Option("-f", "--force", help="Force deletion without confirmation")
    ] = False,
    json_output: JsonOption = False,
) -> None:
    """Remove a task."""
    as_json = json_enabled(ctx, json_output)
    db = ctx.obj.session
    task_id = require_task_id(ctx, task_id, "remove", as_json=as_json)

    # Fetched once up front and reused for both the confirmation prompt and
    # the deletion message, so content is echoed in the destructive
    # confirmation (#57) without a redundant second lookup.
    task = core.get_task(db=db, task_id=task_id)

    prompt_label = (
        f'Delete "{task.content}" (task #{task_id})?'
        if task
        else f"Delete task #{task_id}?"
    )
    require_force(force, prompt_label, as_json=as_json)

    if not task or not core.delete_task(db=db, task_id=task_id):
        if as_json:
            raise json_error(f"Task {task_id} not found.")
        console.print(f"[red]Task {task_id} not found.[/red]")
        raise typer.Exit(code=1)

    if as_json:
        emit_json({"deleted": 1})
        return

    console.print(
        f'[green]\U0001f5d1️  Deleted task #{task_id}: "{task.content}"[/green]'
    )


@app.command()
def clean(
    ctx: typer.Context,
    force: Annotated[
        bool, typer.Option("-f", "--force", help="Force deletion without confirmation")
    ] = False,
    json_output: JsonOption = False,
) -> None:
    """Delete all completed tasks from the database."""
    as_json = json_enabled(ctx, json_output)
    db = ctx.obj.session

    require_force(
        force,
        "Are you sure you want to delete all completed tasks?",
        as_json=as_json,
    )

    count_deleted = core.delete_completed_tasks(db=db)
    if as_json:
        emit_json({"deleted": count_deleted})
        return
    if count_deleted == 0:
        console.print("[yellow]⚠️  No completed tasks to delete.[/yellow]")
    else:
        console.print(
            f"[green]\U0001f9f9 Cleaned {count_deleted} completed tasks.[/green]"
        )


@app.command()
def purge(
    ctx: typer.Context,
    force: Annotated[
        bool, typer.Option("-f", "--force", help="Force deletion without confirmation")
    ] = False,
    json_output: JsonOption = False,
) -> None:
    """Delete all tasks, completely resetting the database."""
    as_json = json_enabled(ctx, json_output)
    db = ctx.obj.session

    if not force and not as_json:
        console.print(
            "[bold red]WARNING: This will permanently delete ALL tasks.[/bold red]"
        )
    require_force(
        force,
        "Are you incredibly sure you want to purge all records?",
        as_json=as_json,
    )

    count_deleted = core.delete_all_tasks(db=db)
    if as_json:
        emit_json({"deleted": count_deleted})
        return
    console.print(
        f"[green]\U0001f9f9 Purged {count_deleted} tasks from the database.[/green]"
    )


@app.command(name="export")
def export_cmd(
    ctx: typer.Context,
    path: Annotated[
        Path | None, typer.Argument(help="File path to save JSON to")
    ] = None,
    done: Annotated[
        bool | None, typer.Option("-d/-t", "--done/--todo", help="Filter by status")
    ] = None,
    category: Annotated[
        str | None, typer.Option("-c", "--category", help="Filter by category")
    ] = None,
    pretty: Annotated[
        bool, typer.Option("-p", "--pretty", help="Pretty print JSON output")
    ] = False,
) -> None:
    """Export tasks to a JSON file.

    A global `--json` flag is accepted but ignored here: `export` already
    produces JSON as its whole purpose, so it has no separate JSON mode.
    """
    db = ctx.obj.session

    count_exported = core.export_tasks(
        db=db, path=path, is_done=done, category=category, pretty=pretty
    )
    if path:
        console.print(f"[green]✅ Exported {count_exported} tasks to {path}[/green]")


@app.command(name="import")
def import_cmd(
    ctx: typer.Context,
    path: Annotated[
        Path,
        typer.Argument(help="File path to read JSON from", exists=True, dir_okay=False),
    ],
    clear: Annotated[
        bool, typer.Option("--clear", help="Purge existing database before importing")
    ] = False,
    json_output: JsonOption = False,
) -> None:
    """Import tasks from a JSON file."""
    as_json = json_enabled(ctx, json_output)
    db = ctx.obj.session

    if clear:
        if not as_json:
            console.print(
                "[bold red]WARNING: This will permanently delete ALL existing "
                "tasks before importing.[/bold red]"
            )
        # --clear's confirmation can't run under --json; require an explicit
        # confirmation channel there, mirroring purge/clean (exit 2).
        if as_json:
            raise json_error("--clear cannot be confirmed in --json mode.", code=2)
        typer.confirm(
            "Are you incredibly sure you want to clear the database?", abort=True
        )

    try:
        count_imported = core.import_tasks(db=db, path=path, clear=clear)
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
        if as_json:
            raise json_error(f"Failed to import tasks: {e}") from e
        console.print(f"[bold red]Failed to import tasks: {e}[/bold red]")
        raise typer.Exit(code=1) from e

    if as_json:
        emit_json({"imported": count_imported})
        return
    console.print(f"[green]✅ Imported {count_imported} tasks from {path}[/green]")


@app.command(name="report")
def report_cmd(
    ctx: typer.Context,
    path: Annotated[Path, typer.Argument(help="File path to save the report to")],
    done: Annotated[
        bool | None, typer.Option("-d/-t", "--done/--todo", help="Filter by status")
    ] = None,
    category: Annotated[
        str | None, typer.Option("-c", "--category", help="Filter by category")
    ] = None,
    sort: Annotated[
        SortField | None,
        typer.Option(
            "-s",
            "--sort",
            help="Sort by field: priority, date, category, status",
        ),
    ] = None,
    reverse: Annotated[
        bool,
        typer.Option("-r", "--reverse", help="Reverse the sort order (descending)"),
    ] = False,
) -> None:
    """Generate a Markdown or HTML report of tasks.

    A global `--json` flag is accepted but ignored: `report` writes its own
    Markdown/HTML artifact and has no JSON mode.
    """
    db = ctx.obj.session

    tasks = core.list_tasks(
        db=db, is_done=done, category=category, sort_by=sort, reverse=reverse
    )

    if not tasks:
        console.print("No tasks found matching criteria.")
        return

    extension = path.suffix.lower()
    if extension == ".md":
        content = core.generate_markdown_report(tasks)
    elif extension in [".html", ".htm"]:
        content = core.generate_html_report(tasks)
    else:
        console.print(
            f"[bold red]Unsupported format: {extension}. Use .md or .html[/bold red]"
        )
        raise typer.Exit(code=1)

    try:
        path.write_text(content, encoding="utf-8")
        console.print(f"[green]✅ Generated report at {path}[/green]")
    except OSError as e:
        console.print(f"[bold red]Failed to write report: {e}[/bold red]")
        raise typer.Exit(code=1) from e


@app.command(name="init-db")
def init_db() -> None:
    """Initialize the database."""
    database.create_db_and_tables()
    console.print("[green]✅ Database initialized successfully.[/green]")


def main() -> None:
    """CLI entrypoint."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
