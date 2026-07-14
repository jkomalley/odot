# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/jkomalley/odot/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/jkomalley/odot/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/jkomalley/odot/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/jkomalley/odot/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/jkomalley/odot/releases/tag/v0.1.1
