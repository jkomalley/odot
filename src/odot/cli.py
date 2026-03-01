"""Typer CLI application."""

import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated
import importlib.metadata

from odot import core, database
from odot.models import TaskCreate, TaskUpdate

app = typer.Typer(
    name="odot", help="A minimalist CLI task manager.", no_args_is_help=True
)
console = Console()


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
        ctx.obj = next(database.get_session())


@app.command()
def add(
    ctx: typer.Context,
    content: str,
    priority: Annotated[
        int, typer.Option("-p", "--priority", help="Priority from 1 to 3")
    ] = 1,
    category: Annotated[
        str, typer.Option("-c", "--category", help="Category label")
    ] = "general",
):
    """Add a new task."""
    db = ctx.obj
    task_data = TaskCreate(content=content, priority=priority, category=category)
    task = core.add_task(db=db, task_data=task_data)
    console.print(f"[green]Added task {task.id}: {task.content}[/green]")


@app.command()
def show(ctx: typer.Context, task_id: int):
    """Show details for a specific task."""
    db = ctx.obj
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
    table.add_row("Created At", local_time.strftime("%Y-%m-%d %H:%M:%S"))

    console.print(table)


@app.command(name="list")
def list_tasks(
    ctx: typer.Context,
    done: Annotated[
        bool | None, typer.Option("-d/-p", "--done/--pending", help="Filter by status")
    ] = None,
):
    """List tasks, optionally filtered by status."""
    db = ctx.obj
    tasks = core.list_tasks(db=db, is_done=done)

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
def update(
    ctx: typer.Context,
    task_id: int,
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
        typer.Option("-d/-p", "--done/--pending", help="Update completion status"),
    ] = None,
):
    """Update properties of an existing task."""
    db = ctx.obj
    update_kwargs = {}
    if content is not None:
        update_kwargs["content"] = content
    if priority is not None:
        update_kwargs["priority"] = priority
    if category is not None:
        update_kwargs["category"] = category
    if done is not None:
        update_kwargs["is_done"] = done

    # If no flags are provided, the map is completely empty
    if not update_kwargs:
        console.print("[yellow]No updates provided.[/yellow]")
        raise typer.Exit(code=1)

    update_data = TaskUpdate(**update_kwargs)

    task = core.update_task(db=db, task_id=task_id, data=update_data)
    if not task:
        console.print(f"[red]Task {task_id} not found.[/red]")
        raise typer.Exit(code=1)

    console.print(f"[green]Successfully updated task {task.id}[/green]")


@app.command()
def rm(ctx: typer.Context, task_id: int):
    """Remove a task."""
    db = ctx.obj
    success = core.delete_task(db=db, task_id=task_id)
    if success:
        console.print(f"[green]Deleted task {task_id}[/green]")
    else:
        console.print(f"[red]Task {task_id} not found.[/red]")
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
