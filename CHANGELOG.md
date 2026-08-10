# Changelog

All notable changes to this project are documented here. Versions follow
[Semantic Versioning](https://semver.org/): MAJOR for breaking changes,
MINOR for backward-compatible additions, PATCH for backward-compatible bug
fixes.

## v1.1.1 — 2026-08-10

### Fixed

- `test-data-builder-usage` skill (`src/claude/test-data-builder-usage/SKILL.md`)
  was still documenting the `v1.1.0` constructor as `Engine`-only. Updated
  the "Where the `Engine`/`Connection`/`Session` comes from" section to
  reflect the `v1.1.0` `Connectable` change, and bumped the install
  snippet's pinned ref from `v1.0.0` to `v1.1.1`. No code change — the
  library itself is unaffected; only the doc/skill lagged the feature it
  documents.
- `test-data-builder-library` skill: documented the `Connectable` decision
  (`Engine | Connection | Session`) and added a standing rule to update
  `test-data-builder-usage` in the same change whenever the public API
  changes, to prevent this kind of drift going forward.

## v1.1.0 — 2026-08-10

### Added

- `TestDataBuilder(connectable, vendor)` now accepts a SQLAlchemy `Connection`
  or `Session` in addition to an `Engine`. Passing a `Connection`/`Session`
  makes the builder execute directly on it and never call `begin()`,
  `commit()`, or `rollback()` itself — the caller's transaction stays fully
  in charge, so a repository test isolated by rolling back a per-test
  transaction can now seed through the builder without rows leaking past
  the rollback. See [doc/issues/3](doc/issues/3/spec.md) and USERGUIDE's
  [Engine, Connection, or Session — which to pass](USERGUIDE.md#engine-connection-or-session--which-to-pass).
- `builder.engine` resolves to the underlying `Engine` regardless of which
  of the three was passed to the constructor.

### Changed

- Nothing behavioral for existing `Engine`-based usage — this release is
  purely additive. `create()`, `delete()`, `apply()`, `count_rows()` behave
  identically to v1.0.0 when constructed with an `Engine`.

## v1.0.0 — initial release

- Python port of the Java `test-data-builder` library: `TestDataBuilder`,
  `Data`, `TestTable`, `TestColumn`, template method patterns, naming
  (`with_name`), `apply()`/`delete()`/`create()` lifecycle.
- PostgreSQL support (`DatabaseVendor.POSTGRESQL`); `MARIADB`/`MYSQL`/`ORACLE`
  declared for shape parity with the Java original but not yet implemented.
