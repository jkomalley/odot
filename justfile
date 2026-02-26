# Justfile for odot project

set shell := ["bash", "-c"]

# Show available recipes
default:
    @just --list

# Initialize the development environment
install:
    uv sync
    pre-commit install

# Run the CLI app locally. Usage: just run --help
run *args:
    uv run odot {{args}}

# Run tests with coverage
test:
    uv run pytest

# Check code formatting (for CI)
format-check:
    uv run ruff format --check .

# Format code
format:
    uv run ruff format .

# Run linter without auto-fixing (for CI)
lint-check:
    uv run ruff check .

# Run linter and auto-fix issues
lint:
    uv run ruff check --fix .

# Run type checks
typecheck:
    uv run ty check

# Run all checks (format, lint, typecheck, tests)
check: format-check lint-check typecheck test

# Clean up cache directories
clean:
    rm -rf .pytest_cache .ruff_cache
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete