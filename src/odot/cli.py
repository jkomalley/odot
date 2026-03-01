"""Typer CLI application."""

import typer
import questionary
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from typing_extensions import Annotated
import importlib.metadata
from sqlmodel import Session

from odot import core, database
from odot.models import TaskCreate, TaskUpdate

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
        ctx.obj = next(database.get_session())


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
        typer.Option("-d/-p", "--done/--pending", help="Update completion status"),
    ] = None,
):
    """Update properties of an existing task."""
    db = ctx.obj
    if task_id is None:
        task_id = prompt_task_selection(db, "update")

    update_kwargs = {}
    if content is not None:
        update_kwargs["content"] = content
    if priority is not None:
        update_kwargs["priority"] = priority
    if category is not None:
        update_kwargs["category"] = category
    if done is not None:
        update_kwargs["is_done"] = done

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
