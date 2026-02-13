# Justfile for odot project
default: sync lint format ty test

# Sync local dependencies with pyproject.toml
sync:
    uv sync

# Run the app locally
run *args:
    uv run odot {{args}}

# Run linter and auto-fix issues
lint:
    uv run ruff check . --fix

# Run linter without auto-fixing (for CI)
lint-ci:
    uv run ruff check .

# Format code
format:
    uv run ruff format

# Check code formatting (for CI)
format-ci:
    uv run ruff format --check

# Run type checks
ty:
    uv run ty check

test:
    uv run pytest

# Run all checks before committing
check: lint ty test