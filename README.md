# TestDataBuilder (Python)

**Stop seeding test data through the code you're trying to test.**

Every project ends up needing to put rows in a database before a repository
or end-to-end test can run. The obvious way — go through your own ORM
models and repositories — quietly wires your test setup to the exact code
path the test exists to catch bugs in. A broken repository, a schema drift,
a subtle mapping bug: the seeding step "succeeds" anyway, because it's using
the same broken code, and your test never notices.

TestDataBuilder seeds with raw SQL instead. No ORM models, no repositories.
Your test data setup stays correct even when the code under test is not —
which is, after all, the point of a test.

This is a Python port of [ovh.heraud:test-data-builder](https://github.com/pascalheraud/test-data-builder)
(Java). **Only PostgreSQL is supported so far** — see
[Supported databases](#supported-databases).

## Why this, not just hand-rolled INSERTs

Raw SQL is the right idea; hand-writing it in every test is not. TestDataBuilder
gives you:

- **Templates** — one method per table, with sane, distinct defaults, so
  `new_customer()` three times in a row never collides on a unique constraint.
- **Foreign keys that resolve themselves** — pass one row as another row's
  column value, and it's wired to the right generated id once both are
  inserted, in the right order.
- **One-call cleanup** — `apply()` deletes what a previous run left behind
  and inserts the new batch, respecting every foreign key automatically, in
  the right direction.
- **The same code for repository tests and end-to-end tests** — it only ever
  needs a SQLAlchemy `Engine`.

## Install

Not published to PyPI (or GitHub Packages) — install directly from this
git repository.

### Poetry

```bash
poetry add --group dev git+https://github.com/pascalheraud/test-data-builder-py.git
```

Pin to a tag or commit instead of always tracking `main` (recommended, so a
teammate's `poetry install` can't silently pick up an unreviewed change):

```bash
poetry add --group dev git+https://github.com/pascalheraud/test-data-builder-py.git#v1.0.0
```

`poetry.lock` then records the exact commit resolved for that ref, so
`poetry install` stays reproducible even if the tag later moves.

### pip

```bash
pip install git+https://github.com/pascalheraud/test-data-builder-py.git@v1.0.0
```

In `requirements.txt` (or `requirements-dev.txt`):

```
test-data-builder @ git+https://github.com/pascalheraud/test-data-builder-py.git@v1.0.0
```

`@v1.0.0` (a tag), `@main` (a branch), or `@<commit-sha>` are all valid —
prefer a tag or commit SHA over a branch for anything checked into a
project's own dependency file, for the same reproducibility reason as above.

### Upgrading

Bump the pinned ref (`#v1.0.1` for Poetry, `@v1.0.1` for pip) and reinstall
— there's no separate registry step, since the git tag/commit *is* the
version.

## A taste of it

```python
from testdatabuilder.generic import Data, DatabaseVendor, TestDataBuilder


class BookstoreTestDataBuilder(TestDataBuilder):

    def new_publisher(self) -> Data:
        publisher = self._new_data(BookstoreTable.PUBLISHER)
        index = publisher.index
        return self._register(publisher.set_column(PublisherColumn.NAME, f"Publisher {index}"))

    def new_book_for_current_publisher(self) -> Data:
        book = self._new_data(BookstoreTable.BOOK)
        return self._register(
            book.set_column(BookColumn.PUBLISHER_ID, self._current(BookstoreTable.PUBLISHER))
        )
```

```python
builder = BookstoreTestDataBuilder(engine, DatabaseVendor.POSTGRESQL)
builder.new_publisher()
builder.new_book_for_current_publisher()
builder.apply()  # deletes leftovers, inserts the new batch, wires the FK
```

Full walkthrough, template patterns: see [USERGUIDE.md](USERGUIDE.md).

## Supported databases

**PostgreSQL only, for now.** The Java original supports PostgreSQL,
MariaDB, MySQL, and Oracle; this port keeps the `DatabaseVendor` enum shape
for the same four vendors, but `TestDataBuilder._resolve_generated_id` only
implements `DatabaseVendor.POSTGRESQL` — the others raise
`NotImplementedError`. Extending to another vendor means implementing that
vendor's generated-id read-back (see the docstring on
`TestDataBuilder._resolve_generated_id`) and adding a schema + test suite
for it, mirroring what exists for PostgreSQL under `tests/`.

## For Claude Code users

- **Using this library in your own project?** Copy
  `src/claude/test-data-builder-usage/` into your project's
  `.claude/skills/` — covers dependency setup and mapping your schema to
  `TestTable`/`TestColumn`/`Data`.
- **Changing this repo's own code?** Load `test-data-builder-library` (in
  this repo's `.claude/skills/`, active while working in this repo) — the
  decisions behind this codebase (Postgres-only scope, the bookstore
  example, API conventions).

## Contributing

Comments, questions, and bug reports are welcome as
[issues](https://github.com/pascalheraud/test-data-builder-py/issues). If
you're thinking about a pull request, open an issue first to discuss the
change — it's much easier to agree on the approach before code gets written
than after.

## License

GPL-3.0 — see [LICENSE](LICENSE).
