# Issue 3 — Implementation plan

Plan derived from [spec.md](./spec.md). Both modes are supported by the same
constructor parameter — its type (`Engine` vs. `Connection`/`Session`)
decides who manages the transaction:

- **`Engine` mode** (existing, unchanged): the builder opens/commits its own
  connection on every `create()`/`delete()`/`count_rows()` call.
- **`Connection`/`Session` mode** (new): the builder only ever executes on
  the object handed in, never begins/commits/rollbacks — the caller's
  transaction (e.g. a rollback-isolated test fixture) is fully in charge.

## 1. `_Connectable` resolution helper

- [ ] In `test_data_builder.py`, add a small internal helper that, given the
  constructor argument, returns:
  - the `Engine` to expose via the `engine` property (`obj` itself if
    `Engine`; `obj.connection().engine` — actually `Connection.engine` /
    `Session.get_bind()` — resolve the right accessor during implementation),
  - a way to obtain something to execute statements on for each operation:
    either "open a fresh connection, run in a `with ... begin()`, commit" (
    `Engine` case), or "reuse the given `Connection` directly, no
    begin/commit" (`Connection` case), or "use `session.connection()`, no
    begin/commit" (`Session` case).
- [ ] Represent this as two code paths behind one private method, e.g.
  `self._execute(fn)` where `fn` receives a `Connection` — `Engine` mode
  wraps the call in `with self._engine.begin() as connection: fn(connection)`
  (today's behavior, verbatim); `Connection`/`Session` mode calls
  `fn(self._connection)` directly with no context manager.
- [ ] Update `__init__` signature: `def __init__(self, connectable: Engine | Connection | Session, vendor: DatabaseVendor) -> None`. Keep the parameter
  positional-compatible with today's `engine` argument (existing
  `TestDataBuilder(engine, DatabaseVendor.POSTGRESQL)` call sites keep
  working unchanged) — decide during implementation whether the parameter
  name itself changes to `connectable` (breaking for keyword callers) or
  stays `engine` (name no longer fully accurate, but zero breakage even for
  keyword use). Default to keeping the name `engine` unless a keyword-arg
  breakage check says otherwise.

## 2. Route `create()` / `delete()` / `count_rows()` through it

- [ ] `create()`: replace `with self._engine.begin() as connection: ...`
  with the new `self._execute(...)` helper — identical body, just no longer
  hardcoded to `self._engine`.
- [ ] `delete()`: same replacement.
- [ ] `count_rows()`: same replacement (currently uses
  `self._engine.connect()`, read-only — confirm whether `Connection` mode
  needs a distinct "no commit needed, it's a SELECT" path or can reuse the
  same helper unconditionally).
- [ ] `_insert()` / `_resolve_generated_id()`: unaffected — they already
  receive a `connection` parameter from the caller, no change needed.

## 3. `engine` property

- [ ] Resolve to the right `Engine` for all three input types:
  - `Engine` input → itself.
  - `Connection` input → `connection.engine`.
  - `Session` input → `session.get_bind()` (confirm this returns the
    `Engine` and not something else when the session isn't bound to
    multiple engines/binds — single-engine session is the only case this
    library needs to support).

## 4. Tests

- [ ] New `tests/test_connectable_behavior.py`:
  - `Connection` case: open `postgres_engine.connect()`, `connection.begin()`
    manually (or rely on autobegin), construct the builder with that
    `Connection`, register + `create()` a row, assert it's visible via a
    `SELECT` on the *same* connection, then `rollback()` the connection and
    assert the row is gone. Assert the builder itself never called
    `commit()`/`rollback()` (e.g. spy/wrap the connection, or simply rely on
    the rollback-makes-it-disappear assertion as the behavioral proof).
  - `Session` case: same shape, using `sessionmaker(bind=postgres_engine)`
    and `Session.rollback()` and `Session.connection()`, seeding through the
    builder mounted on that `Session`, then asserting rollback removes the
    rows.
  - `Engine` case: keep as regression coverage that current behavior is
    unchanged (probably already covered by the existing `builder` fixture in
    `tests/conftest.py` / `test_create_behavior.py` — confirm rather than
    duplicate).
- [ ] Run the full existing suite (`test_create_behavior.py`,
  `test_delete_behavior.py`, `test_index_behavior.py`,
  `test_registration_behavior.py`, `test_template_behavior.py`) to confirm
  zero regressions.

## 5. Docs

- [ ] `USERGUIDE.md`: new section (near "Where the `Engine` comes from")
  explaining the three constructor input types and when to reach for which:
  `Connection`/`Session` for rollback-isolated repository tests,
  `Engine` for e2e/Testcontainers tests with no surrounding transaction.
- [ ] `README.md`: mention the widened constructor type if it currently
  documents the `Engine`-only signature.
- [ ] `src/claude/test-data-builder-usage/SKILL.md` (this repo's copy) and
  the copy already synced into consuming projects (e.g. `danslafoule`'s
  `.claude/skills/third-party/test-data-builder-usage/SKILL.md`): update
  "Where the `Engine` comes from" to reflect that a repository test now
  passes its existing `Connection`/`Session` directly instead of a
  second, session-scoped `Engine` plus manual truncate-on-teardown.

## 6. Versioning

- [ ] Bump `pyproject.toml` version `1.0.0` → `1.1.0`.
- [ ] Update `CHANGELOG` if one exists (none found in this repo today —
  confirm during implementation whether to introduce one or rely on git
  tags/GitHub releases as the only changelog).
- [ ] Tag `v1.1.0` once merged (tagging itself is a git-mutating operation —
  hand the exact `git tag`/`git push` commands back to the project owner
  rather than running them).

## 7. Downstream follow-up (tracked here, not executed as part of this issue)

- [ ] Once `v1.1.0` is published, `danslafoule`'s `backend/tests/conftest.py`
  `builder` fixture can drop its session-scoped `postgres_engine` +
  `with_delete_all(...).delete()` teardown truncate, and instead construct
  `DanslafouleTestDataBuilder` directly on the existing `db_session`
  (`Session`), getting isolation for free from the same rollback the rest
  of that fixture already relies on. Out of scope for this issue itself —
  raised here so it isn't lost.

## Suggested execution order

1. `_Connectable` resolution helper + `__init__` signature change
2. Route `create()`/`delete()`/`count_rows()` through it
3. `engine` property fix
4. New tests (`Connection` + `Session` cases), full suite regression run
5. Docs (`USERGUIDE.md`, `README.md`, both skill copies)
6. Version bump + tag

## Log

<!-- One entry per completed step, newest at the bottom. Format: - YYYY-MM-DD — <step done> — <short note> -->
- 2026-08-10 — Plan drafted from spec.md, not yet started.
