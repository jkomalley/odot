# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`odot` is a minimalist, interactive command-line task manager. Python 3.11+, src layout, managed with `uv`, published to PyPI as `odot`.

## Commands

- **Install deps:** `just install` (`uv sync` + `uv run pre-commit install`)
- **Run the CLI locally:** `just run --help` (`uv run odot --help`)
- **Run tests:** `just test` (`uv run pytest`)
- **Run single test:** `uv run pytest tests/test_core.py::test_name -v`
- **Test with coverage (100% gate):** `just test-cov` (`uv run pytest --cov --cov-fail-under=100`)
- **Format:** `just format` (`uv run ruff format .`)
- **Format check:** `just format-check` (`uv run ruff format --check .`)
- **Lint (auto-fix):** `just lint` (`uv run ruff check --fix .`)
- **Lint check:** `just lint-check` (`uv run ruff check .`)
- **Type check:** `just typecheck` (`uv run ty check`)
- **Everything:** `just check` (format-check + lint-check + typecheck + test-cov)
- **Clean caches:** `just clean`
- **Upgrade lockfile:** `just lock-upgrade`
- **Bump version:** `just bump-version <major|minor|patch|dev|beta|alpha|rc>` (`uv version --bump <part>`)

## Architecture

The project uses a `src/odot/` layout with this module structure:

- `models.py` — SQLModel schemas: `TaskBase` (shared fields: `content`, `priority` 1–3, `category`), `Task` (the `tasks` table, adds `id`, `is_done`, `created_at`, `updated_at`), `TaskCreate` (creation input), `TaskUpdate` (all fields optional, for partial updates).
- `core.py` — Pure CRUD and business logic (add/get/list/search/update/delete tasks, bulk clean/purge, JSON import/export, Markdown/HTML report generation). Operates on a `Session` passed in by the caller; knows nothing about the CLI or presentation layer.
- `database.py` — Engine, session, and path management: `get_db_path()` (honors `ODOT_DB_PATH`), `get_engine()` (lazily-created module-level singleton engine), `create_db_and_tables()`.
- `cli.py` — Typer commands, Rich table/console output, Questionary interactive prompts (used when a required argument like a task ID is omitted).

Key design decisions:

- **The typer/rich/questionary/sqlmodel stack is a deliberate divergence** from the owner's usual argparse/zero-dependency house standard. `odot` is an interactive TUI-style app, and this stack is the pragmatic choice for that — it isn't an oversight.
- **Categories are free-text and case-sensitive by design.** There is no normalization or a fixed enum; `work` and `Work` are different categories. This is documented behavior, not a bug.
- **The database lives at `~/.odot/db.sqlite`** unless the `ODOT_DB_PATH` environment variable overrides it. The database and its parent directory are created automatically on first use.
- **The engine is a process-level singleton** (`database._engine`), created lazily on first `get_engine()` call. Tests replace it with an in-memory engine (see Testing Notes).

## Workflow

- Every feature, fix, or other change gets its own branch and pull request — no direct commits to main.
- Commits must be atomic and follow Conventional Commits (`feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`, `deps`): one logical change per commit.
- PRs that resolve an issue reference it with `Closes #N` so it closes automatically on merge.
- PRs are squash-merged.

## Code Style

- Google-style docstrings (enforced by ruff).
- Line length: 88 chars.
- Ruff `select = ["ALL"]` with a pragmatic, curated set of ignores (see `pyproject.toml`).
- Tests are exempt from docstring and type-annotation rules.
- Prefer comments that explain *why* code does something, not *what* it does.

## Testing Notes

- 100% branch coverage is a hard gate (`--cov-fail-under=100` in `just test-cov` / `just check`) — every new branch needs a test.
- Tests use an in-memory SQLite engine (`sqlite:///:memory:` with `StaticPool`) installed via an autouse fixture in `tests/conftest.py`, so tests never touch the real `~/.odot` database.
- CLI tests use Typer's `CliRunner`.
- Questionary interactive flows are tested by monkeypatching the questionary calls rather than driving a real TTY.
- Use `ODOT_DB_PATH` to point at an isolated database path in any test or manual run that needs to exercise `database.py` outside the in-memory fixture.
