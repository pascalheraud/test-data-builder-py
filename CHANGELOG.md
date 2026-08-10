# Changelog

All notable changes to this project are documented here. Versions follow
[Semantic Versioning](https://semver.org/): MAJOR for breaking changes,
MINOR for backward-compatible additions, PATCH for backward-compatible bug
fixes.

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
