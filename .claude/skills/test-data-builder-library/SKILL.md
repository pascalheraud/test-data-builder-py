---
name: test-data-builder-library
description: Decisions behind this repo's TestDataBuilder library (Python port) — Postgres-only scope, the bookstore example domain, and API conventions specific to this codebase.
---

# TestDataBuilder library (this repo)

For the model itself (`TestDataBuilder`, `Data`, `TestTable`, `TestColumn`,
`SqlExpression`, template patterns, naming, lifecycle), see
[USERGUIDE.md](../../../USERGUIDE.md) or `test-data-builder-usage` — this
skill only captures decisions specific to *this repo's implementation*.

## Update `test-data-builder-usage` whenever the public API changes

`src/claude/test-data-builder-usage/SKILL.md` is the skill copied verbatim
into consuming projects (e.g. `danslafoule`'s
`.claude/skills/third-party/test-data-builder-usage/SKILL.md` — see that
file's own `<!-- Source: ... -->` comment) to teach them how to *consume*
this library. Any change to the public API or its recommended usage —
constructor signature, a new parameter type accepted (e.g. `Connectable`
widening to `Engine | Connection | Session` in v1.1.0), the install
instructions, the pinned version in the install snippet — must update
`test-data-builder-usage` in the same change, not as a follow-up. A
consuming project only ever re-syncs that file by copying it again; it
won't discover a usage-relevant change some other way, so leaving the skill
stale silently breaks the guidance every consumer relies on.

## This is a port of a Java library

This repo (`test-data-builder-py`) is a Python port of
[ovh.heraud:test-data-builder](https://github.com/pascalheraud/test-data-builder).
When changing behavior here, check whether the Java original does the same
thing — an intentional divergence (e.g. Postgres-only scope, below) should
be documented as such; an accidental one is a bug. Method names follow
Python conventions (`snake_case`, `new_publisher()` not `newPublisher()`)
but mirror the Java method 1:1 otherwise.

## Language

English only — code, comments, commit messages, issues, and every doc file
(README, USERGUIDE, CHANGELOG, this skill included), same as the Java
original.

## Postgres-only scope, on purpose

The Java original supports PostgreSQL, MariaDB, MySQL, and Oracle. This
port keeps the `DatabaseVendor` enum shape (all four members, for parity
with the Java API) but only implements `TestDataBuilder._resolve_generated_id`
for `DatabaseVendor.POSTGRESQL` — the other three raise
`NotImplementedError`. This was a deliberate scope decision, not an
oversight: Python DBAPI drivers differ enough between vendors (PostgreSQL's
`RETURNING` clause vs. Oracle's out-bind variables vs. MySQL/MariaDB's
cursor `lastrowid`) that each additional vendor is real, untested work, not
a one-line addition — ship what's verified against a real container first.

**A first attempt at Oracle and MySQL/MariaDB support was written and then
deliberately removed** before this library's first commit, because it was
never tested against a real container and the Oracle path had a live bug
(a dead `str.replace(..., 0)` call and use of SQLAlchemy's deprecated
`Connection.connection` instead of `Connection.driver_connection`). Don't
resurrect that code from git history as if it were known-good — if you add
another vendor, write it against a real Testcontainers instance for that
vendor from scratch, the same way PostgreSQL support was verified.

When adding a vendor: implement its branch in
`TestDataBuilder._resolve_generated_id`, add a
`tests/resources/bookstore-schema-<vendor>.sql`, and add a test suite for
it mirroring `tests/test_*_behavior.py` against a real Testcontainers
instance for that vendor — don't add vendor-specific logic without a test
that actually exercises it end to end.

## `EnumMeta`/`ABCMeta` metaclass conflict — why `TestTable`/`TestColumn` aren't ABCs

`TestTable` and `TestColumn` are plain base classes with methods that raise
`NotImplementedError`, not `abc.ABC` subclasses with `@abstractmethod`. This
was a deliberate correction during the port: `Enum`'s metaclass
(`EnumMeta`) and `ABCMeta` don't compose, and every concrete table/column in
this library (and in a consuming project) is defined as
`class BookColumn(TestColumn, Enum): ...` — mixing `TestColumn`/`TestTable`
in alongside `Enum`. An `ABC`-based version raised
`TypeError: metaclass conflict` the moment a concrete enum tried to inherit
from both. Keep this pattern for any future `TestColumn`/`TestTable`-like
mixin; don't reach for `ABC` there even though it's usually the more
idiomatic choice for a Python interface.

## The bookstore is the one canonical example domain

`src/testdatabuilder/bookstore/` is deliberately the only example domain in
this repo, mirroring the Java original's `src/test/.../bookstore/`. Any
future addition that needs a new template pattern extends the bookstore
schema (a new table/column, a new template method) rather than introducing
a second, unrelated demo domain.

## SQLAlchemy Core as the `DataSource`/`JdbcTemplate` equivalent

`TestDataBuilder.__init__` takes a SQLAlchemy `Engine`, `Connection`, or
`Session` (the `Connectable` type alias in `test_data_builder.py`), the same
role `DataSource` plays in the Java original — the builder never depends on
anything else, so the same builder code works for a repository test and an
E2E test. Raw SQL is built as `sqlalchemy.text()` with named (`:p0`, `:p1`,
...) placeholders rather than positional `?` placeholders (the JDBC/Java
style) — SQLAlchemy's `text()` requires named parameters, and generating
them positionally (`p{column_index}`) avoids any risk of a caller's own SQL
(inside an `SqlExpression`) colliding with a name.

**Since v1.1.0, `Connectable` is `Engine | Connection | Session`, not just
`Engine`** ([doc/issues/3](../../../doc/issues/3/spec.md)). The type
decides who manages the transaction — this is load-bearing, not
incidental, so preserve it in any refactor of `_connect()`:

- `Engine` → the builder opens its own connection and commits, on every
  `create()`/`delete()`/`count_rows()` call (unchanged since v1.0.0). Right
  for an E2E test with no surrounding transaction to roll back.
- `Connection`/`Session` → the builder only ever executes on the object
  given to it. It never calls `begin()`/`commit()`/`rollback()`. Right for
  a repository test isolated by a per-test transaction rollback — passing
  the same `Connection`/`Session` the test fixture already wraps means rows
  the builder inserts vanish with everything else on rollback, with no
  separate truncate/cleanup step (contrast with the "Test isolation:
  `TRUNCATE` in fixture teardown" section below, which predates this and
  is why `tests/conftest.py` here still truncates rather than using this
  mode — this repo's own tests seed through a session-scoped `Engine` on
  purpose, to exercise the `Engine` code path).
- `builder.engine` resolves the underlying `Engine` for all three
  (`Connection.engine` / `Session.get_bind()`) — don't let a future change
  make this property `Engine`-input-only again; project subclasses
  (read-back helper methods) rely on it working regardless of how the
  builder was constructed.

## API conventions for template builders in this repo

Same conventions as the Java original's `test-data-builder-usage`/
`test-data-builder-library` skills, adapted to Python:

- **Read-back helper methods, not inline SQL in tests.** A test asserting
  on state after `create()`/`apply()` calls a named method on the builder
  (`current_book_publisher_id(book)`, `count_rows(table)`) rather than
  building a `SELECT` inline.
- **Don't put "simulate the application" code on the builder.** A few
  tests need to insert/update a row the way the *application under test*
  would (e.g. writing to `order_event`, mutating `orders.status`) — that's
  not seeding, so it stays as plain SQL directly in the test body via
  `builder.engine`, with a comment saying it simulates the app, rather than
  becoming a builder method.
- **Parameterized templates take primitives, not the type they'll become.**
  `new_book(title: str, price: str)` takes `price` as a plain `str` and
  constructs the `Decimal` once, inside the template.

## Test isolation: `TRUNCATE` in fixture teardown, not just `builder.delete()`

`tests/conftest.py` uses a **session-scoped** Postgres Testcontainers
container (starting one per test would dominate the suite's runtime) with a
**function-scoped** `builder` fixture (a fresh `BookstoreTestDataBuilder`
per test, since builder state — registered `Data`, naming scopes, indices —
must not leak between tests). The consequence: a fresh builder instance
has an empty `_to_delete_tables`, so `builder.delete()` in teardown clears
nothing — it only knows about tables *that instance* touched. The fixture
teardown instead issues an explicit
`TRUNCATE <all bookstore tables> RESTART IDENTITY CASCADE` against the
shared engine. This is specific to the fixture design here (fresh builder
per test, shared container) — the Java original's Testcontainers setup
sidesteps this by container/schema-hash-keyed reuse plus (implicitly)
Spring's per-test transaction rollback; this port has no direct equivalent
of that, so tests rely on explicit truncation instead.
