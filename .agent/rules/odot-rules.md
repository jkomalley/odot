# Odot Project Rules

Below are the established rules for developing the `odot` project, based on the current architecture, tech stack, and naming conventions.

## 1. Tech Stack

- **Language**: Python 3.10+
- **CLI Framework**: Typer (`typer[all]`)
- **Database / ORM**: SQLModel (SQLite backend)
- **TUI & Styling**: Questionary (interactive prompts) and Rich (terminal formatting)
- **Task Runner**: `just`
- **Testing**: `pytest`, `pytest-cov`, `typer.testing.CliRunner`
- **Type Checking**: Ty

## 2. Architecture & File Structure

The project employs a clean separation of concerns, divided into four core areas inside the `src/odot/` directory:

- **`models.py`**: Contains all SQLModel definitions. Use base classes to avoid duplicating fields (e.g., `TaskBase`, `TaskCreate`, `TaskUpdate`, `Task`).
- **`database.py`**: Manages the SQLite database connection, engine lifecycle, and `get_session()` dependency provision. Falls back to `~/.odot/db.sqlite` if `ODOT_DB_PATH` is not set.
- **`core.py`**: Contains domain-level CRUD business logic (e.g., `add_task`, `list_tasks`). Functions take a `Session` object and validated data models (`TaskCreate`, `TaskUpdate`) and return `Task` objects or simple native types.
- **`cli.py`**: The Typer application entrypoint. Interacts with the user via `Questionary` and `Rich`, parses CLI arguments, establishes the database session via context (`ctx.obj`), and coordinates with `core.py` to enact changes.
- **Exclusivity of Concern**: The CLI module (`cli.py`) handles all UI, print outputs, and exceptions terminating the app. The Core module (`core.py`) knows nothing about Typer, Rich, or Questionary.

## 3. Naming Conventions

- **Files and Modules**: `snake_case` (e.g., `core.py`, `test_cli.py`).
- **Classes and Models**: `PascalCase` (e.g., `TaskCreate`, `TaskUpdate`).
- **Functions, Methods, Variables**: `snake_case` (e.g., `add_task`, `prompt_task_selection`, `is_done`).
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DATETIME_FORMAT`, `DB_FILE`).
- **CLI Commands**: Command functions should describe the domain action (e.g., `def list_tasks()`), using `@app.command(name="list")` when the function name doesn't exactly match the CLI alias.
- **Typer Arguments**: Use `typing_extensions.Annotated` for CLI arguments and options.

## 4. Testing Patterns

- **Framework**: Use `pytest`.
- **Naming**: Test files must be named `test_<module>.py`. Test functions must be named `test_<behavior>`.
- **Database Testing**:
  - Import the `session` fixture from `conftest.py` which provisions an isolated, fast, in-memory SQLite (`sqlite:///:memory:`) database for every test.
  - The `engine` uses `StaticPool` to prevent threading exceptions during rapid testing.
- **CLI Testing**:
  - Use `CliRunner()` from `typer.testing` to execute CLI commands.
  - Use `monkeypatch.setattr()` alongside the `session` fixture to mock `database.get_session` internally mimicking the actual runtime.
  - Check coverage enforcing using `just test-cov`. The project targets 100% test coverage.

## 5. Development Tools & Workflows

- **`just` Workflows**:
  - Used as the primary operational task runner.
  - Central commands:
    - `just install`: Syncs dependencies and installs hooks.
    - `just check`: Runs the full CI validation locally (formatting, linting, typechecking, and test coverage).
    - `just test-cov`: Runs the complete test suite enforcing a 100% coverage threshold.
    - `just bump-version <part>`: Bumps the project version.

## 6. Continuous Integration & Deployment (GitHub Actions)

- **CI Pipeline (`ci.yml`)**: Runs on pushes to `main` and all Pull Requests. Tests across a multi-version Python matrix (3.10 through 3.14). Relies on `just check` to strictly enforce 100% test coverage and linting on every PR.
- **Version Bumping (`bump-version.yml`)**: A manually dispatched workflow specifying the semver part (major/minor/patch/etc.). It automatically creates a Pull Request (`chore/bump-version`) updating the version.
- **Releases (`release.yml`)**: Triggered natively upon pushing a `v*` tag. Builds the `uv` package and organically publishes to both GitHub Releases and PyPI.
- **Dependabot (`dependabot.yml`)**: Runs weekly scanning for updates to GitHub Actions and `uv` dependencies.
