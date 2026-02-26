# Odot Project Plan & Design

This document outlines the development plan, architecture, and technical specifications for `odot`, a minimalist CLI task manager and Python library.

## 1. Core Philosophy & Goals

-   **Minimalist:** The tool should be simple, fast, and focused on core task management features.
-   **Decoupled:** The core logic (`core.py`) must be a reusable Python library, fully independent of the CLI presentation layer (`main.py`).
-   **Modern & Robust:** Adhere to modern Python conventions, including strict type hinting, clean code, and comprehensive test coverage.
-   **Developer Experience:** Provide a smooth development workflow using best-in-class tooling (`uv`, `ruff`, `ty`, `pytest`).

## 2. Technical Stack

| Category              | Tool                                | Purpose                                   |
| --------------------- | ----------------------------------- | ----------------------------------------- |
| **Language**          | Python 3.10 - 3.14                  | Core programming language                 |
| **Package Management**| `uv`                                | Dependency management and tool runner     |
| **Build System**      | `uv-build`                          | Project build backend                     |
| **CLI Framework**     | Typer                               | Building the command-line interface       |
| **Database ORM**      | SQLModel                            | Data modeling and SQLite interaction      |
| **Terminal Output**   | Rich                                | Pretty printing tables and text           |
| **Linting/Formatting**| Ruff                                | Code quality and style enforcement        |
| **Type Checking**     | `ty`                                | High-performance static type analysis     |
| **Testing**           | Pytest, Pytest-Cov                  | Unit testing and code coverage            |
| **Task Runner**       | `just`                              | Automating development commands           |
| **Git Hooks**         | Pre-commit                          | Running checks before committing code     |

## 3. Architectural Design

The project uses a layered architecture to separate concerns.

### 3.1. File Structure

```
.
├── src/
│   └── odot/
│       ├── __init__.py         # Package initializer, exports version
│       ├── models.py         # SQLModel data models
│       ├── database.py       # Database connection and session management
│       ├── core.py           # Core library logic (CRUD operations)
│       └── main.py           # Typer CLI application
├── justfile                # Command runner recipes
├── pyproject.toml          # Project metadata and tool configuration
└── .pre-commit-config.yaml # Git hook definitions
```

### 3.2. Data Model Layers (`models.py`)

The data models are split into three classes to ensure validation and separation of concerns:

1.  **`TaskBase(SQLModel)`**: Defines the common, shared fields for a task that can be provided during creation or update.
    -   `content: str`
    -   `priority: int | None = None`
    -   `category: str | None = None`
2.  **`TaskCreate(TaskBase)`**: A specific model used *only* for validating data when creating a new task. It inherits from `TaskBase` and has no new fields. It ensures that read-only fields like `id` or `created_at` are not passed in.
3.  **`Task(TaskBase, table=True)`**: The primary database model representing the `task` table in SQLite. It includes all fields, including those managed by the database.
    -   `id: int | None = Field(default=None, primary_key=True)`
    -   `is_done: bool = False`
    -   `created_at: datetime = Field(default_factory=datetime.utcnow)`

## 4. Implementation Plan

### Step 1: Foundational Setup (Complete)

-   [x] Configure `pyproject.toml` with project metadata, dependencies, and tool settings.
-   [x] Configure `justfile` for running common development tasks.
-   [x] Configure `.pre-commit-config.yaml` for automated code quality checks.
-   [x] Establish the initial source file structure.

### Step 2: Database Layer (`database.py`)

-   [ ] Define the SQLite database file path (e.g., in `~/.odot/db.sqlite`).
-   [ ] Create the database engine (`create_engine` from SQLModel).
-   [ ] Implement a function `create_db_and_tables()` to be called on first run.
-   [ ] Implement a dependency provider function `get_session()` that yields a `Session` object for use in CRUD operations.

### Step 3: Core Logic (`core.py`)

-   [ ] Implement CRUD functions that accept a `Session` object via dependency injection.
    -   `add_task(db: Session, task: TaskCreate) -> Task`
    -   `get_task(db: Session, task_id: int) -> Task | None`
    -   `list_tasks(db: Session, is_done: bool | None = None) -> list[Task]`
    -   `update_task(db: Session, task_id: int, data: TaskUpdate) -> Task | None` (Requires a `TaskUpdate` model in `models.py`)
    -   `delete_task(db: Session, task_id: int) -> bool`
-   [ ] Ensure all core logic is pure and does not contain any `print` statements or CLI-specific code.

### Step 4: CLI Application (`main.py`)

-   [ ] Initialize a `typer.Typer()` application instance.
-   [ ] Use Typer's dependency injection system to pass a database session from `get_session()` to each command function.
-   [ ] Implement CLI commands that call the corresponding functions in `core.py`:
    -   `add(content: str, ...)`
    -   `show(task_id: int)`
    -   `list(...)`
    -   `update(task_id: int, ...)`
    -   `rm(task_id: int)`
    -   `init-db()`: A command to explicitly initialize the database.
-   [ ] Use `rich.table.Table` and `rich.console.Console` to display task data in a clean, readable format.

### Step 5: Testing

-   [ ] Create a `tests/` directory.
-   [ ] Write `pytest` unit tests for all functions in `core.py`.
-   [ ] Use `pytest` fixtures to provide an in-memory SQLite database for testing, ensuring tests are isolated and fast.
-   [ ] Write integration tests for the CLI commands.
-   [ ] Monitor test coverage and maintain it above the 80% threshold defined in `pyproject.toml`.
