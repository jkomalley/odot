# odot

A minimalist, interactive command-line task manager built with Python.

`odot` provides a fast and intuitive way to manage your daily tasks directly from your terminal. Built upon Typer and SQLModel, it offers a robust SQLite-backed database with an elegant Terminal User Interface (TUI) for interactive task selection.

## Features

- **Interactive Prompts**: Execute commands without remembering IDs. If you forget to pass an argument, `odot` will display a dynamic Arrow-Key navigable menu to select tasks.
- **Rich Output**: Clean, formatted tables utilizing the `rich` library for high readability.
- **Filtering**: Easily filter missing or completed tasks right from the list command.
- **Local First**: Stores your data securely in a local `.sqlite` database configurable via environment variables.
- **Zero Configuration**: Works out of the box with intelligent defaults.

## Installation

You can install `odot` directly from PyPI using pip, pipx, or uv.

Using pip:

```bash
pip install odot
```

Using pipx (Recommended for isolated CLI application installations):

```bash
pipx install odot
```

Using uv:

```bash
uv tool install odot
```

## Quick Start

Once installed, initialize the database to create the required tables on your local machine.

```bash
odot init-db
```

By default, the database is stored at `~/.odot/db.sqlite`. You can override this by setting the `ODOT_DB_PATH` environment variable.

## Usage

### Adding a Task

You can add a task by passing the content directly, or you can supply priority (`-p`) and category (`-c`) flags.

```bash
odot add "Buy groceries for dinner"
odot add "Submit quarterly report" -p 3 -c work
```

### Listing Tasks

View all of your current tasks in a formatted table.

```bash
odot list
```

You can optionally filter the list by status and category:

```bash
odot list --done               # Show only completed tasks
odot list --todo               # Show only open tasks
odot list --category work      # Show only tasks in the 'work' category
odot list -c personal --todo   # Show open tasks in the 'personal' category
```

### Searching Tasks

Find tasks whose content contains a specific phrase.

```bash
odot search "groceries"
odot search "quarterly report"
```

### Showing a Task

View detailed properties and timestamps for a specific task. If you don't know the ID, simply run `odot show` without arguments to open the interactive selection menu.

```bash
odot show
odot show 1
```

### Updating a Task

Update the properties of an existing task. If you run `odot update` without providing a task ID, it will gracefully open an interactive selection menu to pick a task. Subsequently, if you don't provide any explicit update flags, it will launch a multi-select interactive checklist allowing you to pick exactly which fields to change.

```bash
# Fully interactive mode (Prompts for task, then prompts for fields)
odot update

# Explicit mode
odot update 1 --content "Revised task name" --done --priority 2
```

### Removing a Task

Delete a task from the database permanently. If you don't provide an ID, `odot` will open the interactive selection menu so you can browse for the task to delete. By default, `odot` prompts you for confirmation before execution unless you provide the `--force` flag.

```bash
# Interactive task selection mapping
odot rm
odot rm 1
odot rm 1 --force
```

### Purging All Tasks

Delete all tasks from the database entirely, resetting your task list. Because this is a destructive action, `odot` will display a warning and ask for explicit confirmation unless you use the `--force` flag.

```bash
odot purge          # Prompts for confirmation with a warning
odot purge --force  # Skip confirmation
```

## Development

If you wish to contribute or modify `odot` locally, ensure you have `uv` (for Python dependency management), `gh` (the GitHub CLI, for workflow automation), and `just` (the recipe task runner) installed.

1. Clone the repository.
2. Run `uv sync` to install dependencies.
3. Authenticate the GitHub CLI via `gh auth login`.
4. Use the included `just` workflows to run checks and tests:

```bash
just test        # Run the pytest suite natively
just test-cov    # Run tests and enforce 100% coverage
just check       # Run Ruff formatting, linting, ty typechecks, and test loops
```
