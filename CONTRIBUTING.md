# Contributing to odot

Thanks for your interest in improving `odot`. This guide covers everything you
need to get set up and land a change. For CLI *usage*, see the
[README](README.md).

## Ways to contribute

- **Report a bug** or **request a feature** by [opening an issue](https://github.com/jkomalley/odot/issues).
- **Submit a pull request** for a fix or improvement.

For anything large or behavior-changing, please open an issue to discuss the
approach before investing time in a PR.

## Development setup

**Prerequisites:** Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/jkomalley/odot.git
cd odot
uv sync                    # create the venv and install all dependencies
uv run pre-commit install  # enable the git hooks
```

`just install` does the same two steps in one command.

## Project layout

The package uses a `src/` layout. Each module has a single, focused
responsibility:

| Module | Responsibility |
| --- | --- |
| `models.py` | SQLModel schemas: `TaskBase`, `Task` (the `tasks` table), `TaskCreate`, `TaskUpdate`. |
| `core.py` | Pure CRUD and business logic. Takes a `Session`; knows nothing about the CLI. |
| `database.py` | Engine/session/path management, including the `ODOT_DB_PATH` override and the engine singleton. |
| `cli.py` | Typer commands, Rich output, Questionary interactive prompts. Delegates table/label formatting to `_format.py`. |
| `_format.py` | Presentation helpers shared by the CLI: task-table rendering, priority display, relative time, phrase highlighting. |

## Running checks

The repo uses [`just`](https://github.com/casey/just) as a task runner. Run
everything before pushing:

```bash
just check   # format-check + lint-check + typecheck + test-cov
```

Or run individual tasks:

```bash
just format        # ruff format
just format-check  # ruff format --check
just lint          # ruff check --fix
just lint-check    # ruff check
just typecheck     # ty check
just test          # pytest
just test-cov      # pytest with 100% coverage enforcement
```

Each task maps to a plain `uv run …` command, so you can run them directly if
you'd rather not install `just`.

## Coding standards

- **Style & linting:** [`ruff`](https://docs.astral.sh/ruff/) with `select = ["ALL"]` and a curated
  set of pragmatic ignores (see `pyproject.toml`). Run `just format` and `just lint`
  before committing.
- **Type checking:** the codebase is fully typed; `just typecheck` (`ty`) must pass.
- **Docstrings:** Google-style, on every public function and class.
- **Comments:** explain *why*, not *what*. Lean toward documenting non-obvious
  decisions; skip comments that merely restate the code.
- **Line length:** 88 characters.

### Testing

- **100% branch coverage is required.** Every new code path needs a test; check
  with `just test-cov`.
- Tests must not touch the real `~/.odot` database — use the in-memory SQLite
  fixtures in `tests/conftest.py`, or set `ODOT_DB_PATH` for isolation when a
  test needs an on-disk file.
- CLI tests use Typer's `CliRunner`; interactive (Questionary) flows are tested
  by monkeypatching the prompt calls.

## Pull requests

- Branch off `main`; one logical change per PR.
- Keep commits atomic and use [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`, `deps`).
- Include tests for any new or changed behavior.
- Add a bullet under `## [Unreleased]` in `CHANGELOG.md` for any user-facing
  change, so the changelog is always release-ready (internal-only refactors,
  CI, and docs changes are exempt).
- Reference the issue a PR resolves with `Closes #N` so it closes automatically.
- Make sure `just check` passes cleanly before you open the PR.
- PRs are squash-merged.

CI runs the full check suite against Python 3.11–3.14 on every pull request.

## Releasing

Releases are published to PyPI automatically: the release workflow fires when
CI passes on `main` and publishes whenever `pyproject.toml`'s version isn't
already on PyPI. So a release is just a version bump merged to `main` — once
it lands, the workflow builds the package, publishes it to PyPI, tags the
commit, and publishes a GitHub release whose notes are the `CHANGELOG.md`
section for that version.

Because the notes come straight from `CHANGELOG.md`, keep it current as you go
(see the changelog bullet under [Pull requests](#pull-requests)). Cutting a
release is then a `chore: release vX.Y.Z` PR that, in one commit:

- bumps the version (below),
- renames `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` and adds a fresh empty
  `## [Unreleased]` above it, and
- updates the compare links at the bottom of `CHANGELOG.md`.

If the bumped version has no `CHANGELOG.md` section, the release workflow fails
rather than shipping empty notes.

Choose the bump from the changes since the **last release tag**, not just your
latest work:

```bash
git log "$(git describe --tags --abbrev=0)"..HEAD --oneline
```

Map the conventional-commit types in that range to a [semver](https://semver.org/)
bump and apply it with `just`:

| Changes since last release | Bump | Command |
| --- | --- | --- |
| Any `feat:` | minor | `just bump-version minor` |
| Only `fix:` / `docs:` / `chore:` | patch | `just bump-version patch` |
| A breaking change (`feat!:`, `BREAKING CHANGE`) | major¹ | `just bump-version major` |

¹ While the project is pre-1.0, breaking changes are released as a **minor**
bump per semver's 0.x convention.

Open the bump as its own PR. The `version-guard` CI job enforces this: it fails
any release PR whose bump is too small for the commits since the last release
(for example, shipping a `feat:` in a patch). Features merged to `main` without
a release accumulate, so the bump must account for all of them — not just the
most recent change.

## License

By contributing, you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
