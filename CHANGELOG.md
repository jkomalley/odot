# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-07-14

### Added

- `odot count` command with the same `--done/--todo` and `--category` filters as `list` (#58)
- Global `--json` flag: machine-readable output for list/search/show/add/update/done/undo/count, status objects for rm/clean/purge/import; prompts are disabled under `--json` (#62)
- Color-coded priority indicators (`● Low` / `●● Med` / `●●● High`) in task tables (#54)
- Summary counts footer under `odot list` (#55)
- Relative timestamps ("2h ago") alongside absolute times in `odot show` (#56)
- Search results highlight the matched phrase (#60)
- Running bare `odot` now shows the task list instead of help (#61)
- Interactive task selection shows status, category, and priority, supports type-to-filter, and switches to an autocomplete prompt for 20+ tasks (#63)
- `python -m odot` entry point
- PEP 561 `py.typed` marker — the package now ships type information
- Project docs: CONTRIBUTING.md, CLAUDE.md, and this changelog
- Automated releases: merging an unpublished version to main now publishes to PyPI, tags, and drafts a GitHub release; a version-guard CI check enforces semver-correct bumps

### Changed

- Friendlier, more informative success and confirmation messages across all commands; `update` now shows a before/after diff (#57)
- Invalid `--sort` values are rejected at parse time with a usage error (exit 2)
- Search matching is now explicitly case-insensitive rather than relying on SQLite's ASCII-only default
- Core API: `list_tasks` raises `ValueError` on invalid sort fields (#47), `export_tasks` accepts an output stream (#48), new public `set_engine()`/`reset_engine()` (#52)
- Tooling: ruff `select=["ALL"]` with curated ignores, ty type checking, 100% branch-coverage gate

### Removed

- Python 3.10 support — odot now requires Python 3.11+

## [0.3.0] - 2026-05-17

### Added

- `done` and `undo` commands: mark a task complete with `odot done <id>`
  (or interactively) and revert with `odot undo <id>`.
- The database now auto-initializes on first use — no need to run
  `odot init-db` before adding a task.

### Fixed

- Task content and category names are now HTML-escaped in generated reports,
  preventing XSS in report output.

### Changed

- Dependency updates: sqlmodel 0.0.38, ruff 0.15.9, ty 0.0.29, pytest-cov
  7.1.0, uv-build, softprops/action-gh-release.

## [0.2.1] - 2026-03-06

### Changed

- Modernized the README: badges, cleaner layout, and updated usage examples.

## [0.2.0] - 2026-03-06

### Added

- Category filtering on the task list via `--category`.
- `odot search <phrase>` to find tasks by keyword.
- Clear commands to remove all tasks, or only completed ones.
- JSON import/export via `odot export` and `odot import`.
- List sorting by priority, date, category, or status via `--sort`.
- An `updated_at` timestamp tracking when a task was last modified.
- Markdown and HTML report generation.

### Fixed

- Renamed the `--pending` flag to `--todo` to resolve a collision with `-p`
  (priority).
- Replaced a leaky session generator with explicit `ctx.call_on_close`
  cleanup.

## [0.1.1] - 2026-03-01

### Added

- `just lock-upgrade` now opens a pull request automatically when dependency
  updates change the lockfile.

### Changed

- CI hardened to enforce branch protection against direct lockfile upgrades.
- Dependency updates: sqlmodel 0.0.37, ruff 0.15.4, ty 0.0.19, rich 14.3.3,
  actions/checkout v6, astral-sh/setup-uv v7.

### Fixed

- Resolved a duplicate auth header that caused the bump-version workflow to
  fail.

[Unreleased]: https://github.com/jkomalley/odot/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/jkomalley/odot/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/jkomalley/odot/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/jkomalley/odot/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/jkomalley/odot/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/jkomalley/odot/releases/tag/v0.1.1
