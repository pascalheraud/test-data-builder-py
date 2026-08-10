# Issue 3 — Let TestDataBuilder use a caller-provided Connection/Session

## Purpose

`TestDataBuilder` currently only accepts a SQLAlchemy `Engine`, and every
`create()`/`delete()`/`apply()`/`count_rows()` call opens its own connection
via `engine.begin()` (or `engine.connect()`) and commits before returning.
This makes it impossible to seed data through a connection/session a caller
already has open inside a transaction it controls the lifecycle of — most
notably a per-test transaction that gets rolled back in teardown, the
standard SQLAlchemy pattern for isolating repository tests without
recreating the schema per test.

Consuming projects that use this rollback-isolation pattern currently can't
use `TestDataBuilder` for insertion at all: pointing it at the same `Engine`
that pattern also uses commits real rows outside the test's transaction, so
they survive the rollback and leak into the next test. The only workaround
today is falling back to ORM/raw-SQL seeding for anything touching a
rollback-isolated table, defeating the point of having the builder.

## Context

Discovered while wiring `test-data-builder-py` v1.0.0 into a consuming
project (`danslafoule`) whose backend tests isolate via a single `Connection`
wrapped in an outer transaction, rolled back in a `db_session` pytest
fixture's teardown (see `.claude/skills/languages/python/tooling/testcontainers/SKILL.md`
and `tooling/testcontainers` for the general pattern). `TestDataBuilder`
being `Engine`-only forced that project to give the builder its own
session-scoped `Engine` instead and truncate the seeded table explicitly in
a teardown fixture — workable, but a second, inconsistent isolation
mechanism living alongside the project's existing rollback-based one, purely
because the library couldn't participate in it.

## Objectives

### 1. Accept a `Connection` or `Session` in addition to an `Engine`

`TestDataBuilder.__init__` accepts `Engine | Connection | Session` instead of
`Engine` only. The type of object passed determines whether the builder
manages its own transaction lifecycle or defers to the caller's:

- **`Engine`** (today's behavior, unchanged): every `create()`/`delete()`/
  `count_rows()` call opens its own connection, executes, and commits before
  returning. Nothing here changes — existing consumers relying on this
  keep working exactly as before.
- **`Connection`**: statements execute directly on the given connection.
  The builder never calls `begin()`, `commit()`, or `rollback()` on it —
  whatever transaction the caller already opened (or SQLAlchemy 2.0
  "autobegin" lazily opens) stays entirely under the caller's control, so a
  caller-driven rollback undoes everything the builder inserted.
- **`Session`**: resolved to `session.connection()` internally, then treated
  like the `Connection` case above (no begin/commit/rollback) — lets a
  caller hand over the ORM `Session` it already has (e.g. a repository
  test's `db_session` fixture) without reaching for `.connection()` itself.

### 2. `engine` property stays meaningful for all three

`TestDataBuilder.engine` (used today by project-specific subclasses for
read-back helper methods, and by `count_rows()`) resolves to the underlying
`Engine` regardless of which of the three was passed in, so existing
subclass code that reads `self.engine` doesn't need to branch on how the
builder was constructed.

### 3. Document the tradeoff

`USERGUIDE.md` and the `test-data-builder-usage` skill gain a section
explaining when to pass a `Connection`/`Session` (rollback-isolated
repository tests) versus an `Engine` (e2e tests seeding through a
Testcontainers instance with no surrounding transaction to roll back —
`apply()`'s own delete-then-insert is the cleanup mechanism there instead).

## Expected deliverables

- `TestDataBuilder.__init__` accepts `Engine | Connection | Session`.
- `create()`, `delete()`, `count_rows()` (and anything else opening its own
  transaction today) branch on the stored connectable's type instead of
  unconditionally calling `self._engine.begin()`/`.connect()`.
- `engine` property resolves correctly for all three input types.
- Existing `Engine`-based behavior is unchanged — this is purely additive.
- New tests covering the `Connection` and `Session` cases: rows inserted
  through the builder are visible to a query on the same connection/session
  before commit, and disappear after the caller rolls back — without the
  builder itself ever issuing a commit or rollback.
- `USERGUIDE.md` and `test-data-builder-usage` skill updated with the new
  section and a corrected/expanded "Where the `Engine` comes from" table.
- Version bumped to `1.1.0` (`pyproject.toml`), tagged `v1.1.0` once merged.

## Acceptance criteria

- A `TestDataBuilder` constructed with a `Connection` that's part of an
  outer, not-yet-committed transaction: `create()`/`apply()` insert rows
  visible on that same connection, and a caller-issued `rollback()` on that
  transaction removes them — with no commit/rollback ever invoked by the
  builder itself.
- Passing a `Session` behaves identically, via `session.connection()`.
- Passing an `Engine` behaves exactly as in v1.0.0 — no observable behavior
  change, no consuming project needs to touch its `Engine`-based usage.
- `self.engine` returns a proper `Engine` instance in all three cases.
- Full existing test suite (`tests/test_create_behavior.py`,
  `test_delete_behavior.py`, `test_index_behavior.py`,
  `test_registration_behavior.py`, `test_template_behavior.py`) still
  passes unmodified.

## Non-goals

- No change to `DatabaseVendor`/vendor-specific `_resolve_generated_id`
  logic — this issue is only about which object executes the SQL, not how
  generated ids are read back.
- No support for a raw DBAPI connection/cursor — SQLAlchemy `Engine`,
  `Connection`, or `Session` only.
- No change to `apply()`'s delete-then-create semantics, `with_delete_all`,
  or naming (`with_name`) — orthogonal to this issue.
- Not attempting to auto-detect whether a passed `Connection` is already
  inside a transaction and warn otherwise — SQLAlchemy 2.0's autobegin
  makes that unnecessary; the builder just executes and never manages the
  transaction boundary itself when given a `Connection`/`Session`.

## Assumptions

- Consuming projects on SQLAlchemy 2.0 (already the pinned dependency
  range: `sqlalchemy = "^2.0"`).
- A `Session`'s `.connection()` call is safe to invoke repeatedly across
  several builder operations (SQLAlchemy returns the same open connection
  for the session's current transaction) — to confirm during implementation,
  not assumed to need special caching.

## Questions resolved or to confirm with the project

- Constructor parameter name: kept as the existing first positional
  parameter (currently `engine`) — widening its accepted type rather than
  adding a second, mutually-exclusive parameter, to avoid an API surface
  where callers must pick the right one of two named parameters.
- No separate opt-in flag (e.g. `manage_transaction=False`) — the object's
  type alone determines the behavior, since `Connection`/`Session` vs.
  `Engine` already unambiguously signals "caller owns the transaction" vs.
  "give me something to open one from".

## Next step

Produce an implementation plan (`plan.md`) breaking this down into
constructor/type-detection changes, the `create()`/`delete()`/`count_rows()`
refactor, new tests, doc updates, and the version bump.
