"""Typer CLI application."""

import typer

app = typer.Typer(
    name="odot", help="A minimalist CLI task manager.", no_args_is_help=True
)


@app.command()
def add(content: str):
    """Add a new task."""
    pass


@app.command()
def show(task_id: int):
    """Show a task."""
    pass


@app.command(name="list")
def list_tasks():
    """List all tasks."""
    pass


@app.command()
def update(task_id: int):
    """Update a task."""
    pass


@app.command()
def rm(task_id: int):
    """Remove a task."""
    pass


@app.command(name="init-db")
def init_db():
    """Initialize the database."""
    print("Initializing database...")


def main():
    """CLI entrypoint."""
    app()


if __name__ == "__main__":
    main()
