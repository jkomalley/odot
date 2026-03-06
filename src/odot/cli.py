"""Typer CLI application."""

import typer
import questionary
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from typing_extensions import Annotated
import importlib.metadata
from sqlmodel import Session
from typing import Any
from pathlib import Path

from odot import core, database
from odot.models import TaskCreate, TaskUpdate

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

app = typer.Typer(
    name="odot", help="A minimalist CLI task manager.", no_args_is_help=True
)
console = Console()


def prompt_task_selection(db: Session, action: str) -> int:
    """Prompt the user to select a task using an interactive TUI list."""
    tasks = core.list_tasks(db=db)
    if not tasks:
        console.print("[yellow]No tasks available.[/yellow]")
        raise typer.Exit()

    choices = [
        questionary.Choice(
            title=f"ID {t.id} │ {t.content} [{'✔' if t.is_done else '○'}]", value=t.id
        )
        for t in tasks
    ]

    task_id = questionary.select(f"Select a task to {action}:", choices=choices).ask()

    if task_id is None:
        console.print("[yellow]Operation cancelled.[/yellow]")
        raise typer.Exit()

    return task_id


def version_callback(value: bool):
    """Callback for version printing."""
    if value:
        version = importlib.metadata.version("odot")
        console.print(f"odot version: {version}")
        raise typer.Exit()


@app.callback()
def main_callback(
    ctx: typer.Context,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            callback=version_callback,
            is_eager=True,
            help="Show the application's version and exit.",
        ),
    ] = None,
):
    """A minimalist CLI task manager."""
    # Ensure ctx.obj is initialized
    if getattr(ctx, "obj", None) is None:
        session = Session(database.get_engine())
        ctx.obj = session
        ctx.call_on_close(session.close)


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
):
    """Add a new task."""
    if content is None:
        content = Prompt.ask("Task content")

    db = ctx.obj
    task_data = TaskCreate(content=content, priority=priority, category=category)
    task = core.add_task(db=db, task_data=task_data)
    console.print(f"[green]Added task {task.id}: {task.content}[/green]")


@app.command()
def show(
    ctx: typer.Context,
    task_id: Annotated[int | None, typer.Argument(help="Task ID to show")] = None,
):
    """Show details for a specific task."""
    db = ctx.obj
    if task_id is None:
        task_id = prompt_task_selection(db, "show")
    task = core.get_task(db=db, task_id=task_id)
    if not task:
        console.print(f"[red]Task {task_id} not found.[/red]")
        raise typer.Exit(code=1)

    table = Table(title=f"Task {task.id}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Content", task.content)
    table.add_row("Priority", str(task.priority))
    table.add_row("Category", task.category)
    table.add_row("Status", "Done" if task.is_done else "Pending")

    local_time = task.created_at.astimezone()
    table.add_row("Created At", local_time.strftime(DATETIME_FORMAT))

    if task.updated_at:
        local_updated = task.updated_at.astimezone()
        table.add_row("Updated At", local_updated.strftime(DATETIME_FORMAT))

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
        str | None,
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
):
    """List tasks, optionally filtered and sorted confidently seamlessly beautifully flawlessly correctly cleanly appropriately properly effortlessly."""
    db = ctx.obj

    if sort and sort.lower() not in ["priority", "date", "category", "status"]:
        console.print(f"[bold red]Invalid sort field: {sort}[/bold red]")
        raise typer.Exit(code=1)

    tasks = core.list_tasks(
        db=db,
        is_done=done,
        category=category,
        sort_by=sort,
        reverse=reverse,
    )

    if not tasks:
        console.print("No tasks found.")
        return

    table = Table(title="Odot Tasks")
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Status", style="green")
    table.add_column("Priority", justify="right")
    table.add_column("Category", style="blue")
    table.add_column("Content")

    for task in tasks:
        status_str = "[green]✓[/]" if task.is_done else "[yellow]○[/]"
        table.add_row(
            str(task.id), status_str, str(task.priority), task.category, task.content
        )

    console.print(table)


@app.command()
def search(
    ctx: typer.Context,
    phrase: Annotated[str, typer.Argument(help="Phrase to search for in task content")],
):
    """Search for tasks containing a specific phrase."""
    db = ctx.obj
    tasks = core.search_tasks(db=db, phrase=phrase)

    if not tasks:
        console.print(f"No tasks matching '{phrase}' found.")
        return

    table = Table(title="Search Results")
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Status", style="green")
    table.add_column("Priority", justify="right")
    table.add_column("Category", style="blue")
    table.add_column("Content")

    for task in tasks:
        status_str = "[green]✓[/]" if task.is_done else "[yellow]○[/]"
        table.add_row(
            str(task.id), status_str, str(task.priority), task.category, task.content
        )

    console.print(table)


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
):
    """Update properties of an existing task."""
    db = ctx.obj
    if task_id is None:
        task_id = prompt_task_selection(db, "update")

    # Map the explicitly provided arguments into our update explicitly checking local scope
    provided_args = {
        "content": content,
        "priority": priority,
        "category": category,
        "is_done": done,
    }
    update_kwargs: dict[str, Any] = {
        k: v for k, v in provided_args.items() if v is not None
    }

    # If no flags are provided, ask interactively via a checkbox form
    if not update_kwargs:
        choices = questionary.checkbox(
            "Select fields to update:",
            choices=["content", "priority", "category", "done"],
        ).ask()

        if not choices:
            console.print("[yellow]No updates provided.[/yellow]")
            raise typer.Exit(code=1)

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

    update_data = TaskUpdate(**update_kwargs)

    task = core.update_task(db=db, task_id=task_id, data=update_data)
    if not task:
        console.print(f"[red]Task {task_id} not found.[/red]")
        raise typer.Exit(code=1)

    console.print(f"[green]Successfully updated task {task.id}[/green]")


@app.command()
def rm(
    ctx: typer.Context,
    task_id: Annotated[int | None, typer.Argument(help="Task ID to remove")] = None,
    force: Annotated[
        bool, typer.Option("-f", "--force", help="Force deletion without confirmation")
    ] = False,
):
    """Remove a task."""
    db = ctx.obj
    if task_id is None:
        task_id = prompt_task_selection(db, "remove")

    if not force:
        typer.confirm(f"Are you sure you want to delete task {task_id}?", abort=True)
    success = core.delete_task(db=db, task_id=task_id)
    if success:
        console.print(f"[green]Deleted task {task_id}[/green]")
    else:
        console.print(f"[red]Task {task_id} not found.[/red]")
        raise typer.Exit(code=1)


@app.command()
def clean(
    ctx: typer.Context,
    force: Annotated[
        bool, typer.Option("-f", "--force", help="Force deletion without confirmation")
    ] = False,
):
    """Delete all completed tasks from the database."""
    db = ctx.obj

    if not force:
        typer.confirm(
            "Are you sure you want to delete all completed tasks?", abort=True
        )

    count = core.delete_completed_tasks(db=db)
    if count == 0:
        console.print("[yellow]No completed tasks to delete.[/yellow]")
    else:
        console.print(f"[green]Deleted {count} completed tasks.[/green]")


@app.command()
def purge(
    ctx: typer.Context,
    force: Annotated[
        bool, typer.Option("-f", "--force", help="Force deletion without confirmation")
    ] = False,
):
    """Delete all tasks, completely resetting the database."""
    db = ctx.obj

    if not force:
        console.print(
            "[bold red]WARNING: This will permanently delete ALL tasks.[/bold red]"
        )
        typer.confirm(
            "Are you incredibly sure you want to purge all records?", abort=True
        )

    count = core.delete_all_tasks(db=db)
    console.print(f"[green]Purged {count} tasks from the database.[/green]")


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
):
    """Export tasks to a JSON file."""
    db = ctx.obj

    count = core.export_tasks(
        db=db, path=path, is_done=done, category=category, pretty=pretty
    )
    if path:
        console.print(f"[green]Successfully exported {count} tasks to {path}[/green]")


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
):
    """Import tasks from a JSON file."""
    db = ctx.obj

    if clear:
        console.print(
            "[bold red]WARNING: This will permanently delete ALL existing tasks before importing.[/bold red]"
        )
        typer.confirm(
            "Are you incredibly sure you want to clear the database?", abort=True
        )

    try:
        count = core.import_tasks(db=db, path=path, clear=clear)
        console.print(f"[green]Successfully imported {count} tasks from {path}[/green]")
    except Exception as e:
        console.print(f"[bold red]Failed to import tasks: {e}[/bold red]")
        raise typer.Exit(code=1)


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
        str | None,
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
):
    """Generate a Markdown or HTML report of tasks."""
    db = ctx.obj

    if sort and sort.lower() not in ["priority", "date", "category", "status"]:
        console.print(f"[bold red]Invalid sort field: {sort}[/bold red]")
        raise typer.Exit(code=1)

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
        console.print(f"[green]Successfully generated report at {path}[/green]")
    except Exception as e:
        console.print(f"[bold red]Failed to write report: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command(name="init-db")
def init_db():
    """Initialize the database."""
    database.create_db_and_tables()
    console.print("[green]Database initialized successfully.[/green]")


def main():
    """CLI entrypoint."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
