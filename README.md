# odot

[![CI](https://github.com/jkomalley/odot/actions/workflows/ci.yml/badge.svg)](https://github.com/jkomalley/odot/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/odot)](https://pypi.org/project/odot/)
[![Python](https://img.shields.io/pypi/pyversions/odot)](https://pypi.org/project/odot/)
[![License: MIT](https://img.shields.io/github/license/jkomalley/odot)](LICENSE)

A minimalist, interactive command-line task manager built with Python.

---

## Features

- **Interactive prompts** — arrow-key navigable menus when you omit an argument
- **Rich output** — clean, formatted tables via the `rich` library
- **Filtering & sorting** — slice your task list by status, category, priority, or date
- **Import / export** — move tasks between machines with JSON
- **Reports** — generate Markdown or HTML reports with one command
- **Local first** — SQLite-backed, zero-configuration, works offline

## Installation

```bash
# pipx (recommended)
pipx install odot

# uv
uv tool install odot

# pip
pip install odot
```

## Quick Start

```bash
odot init-db                          # create the local database
odot add "Buy groceries" -p 2 -c home # add a task
odot list                             # view all tasks
odot list --todo --sort priority      # open tasks, sorted by priority
```

> The database defaults to `~/.odot/db.sqlite`.
> Override with the `ODOT_DB_PATH` environment variable.

## Usage

### Managing Tasks

```bash
odot add "Submit quarterly report" -p 3 -c work   # add
odot show                                          # interactive detail view
odot update                                        # interactive update
odot update 1 --content "Revised name" --done      # explicit update
odot rm                                            # interactive delete
odot rm 1 --force                                  # skip confirmation
```

### Searching & Filtering

```bash
odot search "groceries"
odot list --done                       # completed tasks only
odot list -c work --todo               # open work tasks
odot list --sort priority --reverse    # descending priority
```

### Import, Export & Reports

```bash
odot export backup.json --todo         # export open tasks
odot import backup.json                # append from file
odot import backup.json --clear        # replace all tasks
odot report tasks.md --sort priority   # Markdown report
odot report work.html --todo -c work   # filtered HTML report
```

### Bulk Operations

```bash
odot clean          # remove completed tasks (prompts for confirmation)
odot clean --force  # skip confirmation
odot purge          # remove all tasks (prompts for confirmation)
odot purge --force  # skip confirmation
```

## Development

Prerequisites: [`uv`](https://docs.astral.sh/uv/), [`just`](https://github.com/casey/just), [`gh`](https://cli.github.com/)

```bash
git clone https://github.com/jkomalley/odot.git && cd odot
uv sync
```

```bash
just test          # run pytest
just test-cov      # enforce 100% coverage
just check         # ruff + ty + tests
```

## License

[MIT](LICENSE)
