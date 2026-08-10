# TestDataBuilder User Guide (Python)

## The problem

Seeding a database for a repository or end-to-end test through your own ORM
models or repositories couples test setup to the exact code the test is
meant to exercise. When that code has a bug — a broken mapping, a schema
drift, a repository method that silently does the wrong thing — the seeding
step doesn't fail loudly. It just seeds slightly wrong data, and the test
built on top of it passes or fails for the wrong reason. Worse, a bug in a
repository can mask itself: the same broken code both writes and reads the
test's fixture, so it's internally "consistent" and nothing looks wrong.

## The fix

TestDataBuilder inserts rows with raw SQL, built from a table name and a
column map — nothing that touches an ORM model or a repository. Test data
setup can't be broken by the code under test, because it never calls into
it. The same builder code works unmodified for a repository test (using
whatever SQLAlchemy `Engine`, `Connection`, or `Session` your test framework
already manages) and for an end-to-end test (using an `Engine` built
directly from a Testcontainers database) — see
[Engine, Connection, or Session — which to pass](#engine-connection-or-session--which-to-pass)
below.

## Install

```bash
poetry add --group dev git+https://github.com/pascalheraud/test-data-builder-py.git
```

## Five-minute walkthrough

Say your project has `publisher` and `book` tables, `book.publisher_id`
referencing `publisher.id`.

### 1. One enum per table, one enum per table's columns

```python
from enum import Enum
from testdatabuilder.generic import TestColumn, TestTable


class PublisherColumn(TestColumn, Enum):
    ID = "id"
    NAME = "name"

    @property
    def sql_name(self) -> str:
        return self.value


class BookColumn(TestColumn, Enum):
    ID = "id"
    TITLE = "title"
    PUBLISHER_ID = "publisher_id"

    @property
    def sql_name(self) -> str:
        return self.value


class MyTable(TestTable, Enum):
    PUBLISHER = ("publisher", PublisherColumn)
    BOOK = ("book", BookColumn)

    def __init__(self, sql_name, column_enum):
        self._sql_name = sql_name
        self._column_enum = column_enum

    @property
    def sql_name(self) -> str:
        return self._sql_name

    @property
    def columns(self):
        return list(self._column_enum)
```

`TestColumn`/`TestTable` are plain base classes (not ABCs) — Python's
`EnumMeta` and `ABCMeta` don't compose, and every table/column enum needs to
mix one of these in alongside `Enum`.

### 2. A builder, one method per table

```python
from testdatabuilder.generic import Data, TestDataBuilder


class MyTestDataBuilder(TestDataBuilder):

    def new_publisher(self) -> Data:
        publisher = self._new_data(MyTable.PUBLISHER)
        index = publisher.index
        return self._register(publisher.set_column(PublisherColumn.NAME, f"Publisher {index}"))

    def new_book_for_current_publisher(self) -> Data:
        book = self._new_data(MyTable.BOOK)
        index = book.index
        return self._register(
            book.set_column(BookColumn.TITLE, f"Book {index}")
            .set_column(BookColumn.PUBLISHER_ID, self._current(MyTable.PUBLISHER))
        )
```

`self._new_data(table)` gives you a blank row tagged with a fresh,
table-scoped index — use it to make each call's defaults distinct
(`f"Publisher {index}"` never collides). `self._current(table)` gives you
the most recently registered row for that table — that's how
`new_book_for_current_publisher()` wires the foreign key without the caller
passing anything.

### 3. Use it in a test

```python
builder = MyTestDataBuilder(engine, DatabaseVendor.POSTGRESQL)

publisher = builder.new_publisher()
book = builder.new_book_for_current_publisher()
builder.apply()

# book.generated_id and publisher.generated_id are now populated
```

See [`apply()`, `delete()`, `create()`: which one to call](#apply-delete-create-which-one-to-call)
below for what each one does and when to reach for it individually instead
of `apply()`.

## Engine, Connection, or Session — which to pass

`TestDataBuilder(connectable, vendor)` accepts an `Engine`, a `Connection`,
or a `Session` as `connectable` — whichever you pass determines who manages
the transaction:

- **`Engine`** — the builder opens and commits its own connection on every
  `create()`/`delete()`/`count_rows()` call. Use this for an **end-to-end
  test**: an `Engine` built from a Testcontainers database, with no
  surrounding transaction to roll back — `apply()`'s delete-then-insert is
  the cleanup mechanism there.
- **`Connection`** or **`Session`** — the builder only ever executes on the
  object you gave it. It never calls `begin()`, `commit()`, or `rollback()`
  itself. Use this for a **repository test isolated by transaction
  rollback**: pass the same `Connection`/`Session` your test fixture already
  wraps in an outer transaction, and rows the builder inserts disappear
  along with everything else when that transaction is rolled back in
  teardown — no separate cleanup step needed.

```python
# Repository test: reuse the fixture's own Session, isolated by rollback
def test_something(db_session: Session) -> None:
    builder = MyTestDataBuilder(db_session, DatabaseVendor.POSTGRESQL)
    builder.new_publisher()
    builder.create()  # not apply() — nothing to delete, the transaction
                       # started clean and will be rolled back after the test
    ...

# End-to-end test: a plain Engine, no surrounding transaction
def test_something_e2e(app_url: str) -> None:
    engine = create_engine(testcontainers_connection_url)
    builder = MyTestDataBuilder(engine, DatabaseVendor.POSTGRESQL)
    builder.new_publisher()
    builder.apply()  # delete() then create() — the cleanup mechanism here
    ...
```

`builder.engine` resolves to the underlying `Engine` in all three cases
(`Connection.engine` / `Session.get_bind()` under the hood), so
project-specific subclass code (e.g. a read-back helper method) never needs
to know or care which of the three the builder was constructed with.

## `apply()`, `delete()`, `create()`: which one to call

`apply()` is `delete()` then `create()` — the right call for the normal
case (seed a scenario, then run it). The two halves exist separately for
the cases where combining them isn't what you want:

| Call | Deletes | Inserts | Use it alone when |
|---|---|---|---|
| `create()` | nothing | every registered `Data` not yet inserted | you know the tables are already clean (a fresh Testcontainers database, or a repository test relying on transaction rollback for isolation) and don't want a no-op `DELETE` pass, or you're adding a second batch mid-test after `apply()` already ran once (see below) |
| `delete()` | every table this builder has touched, in the right order | nothing | you want to assert on an empty/cleaned-up state directly, without immediately reseeding |
| `apply()` | (via `delete()`) | (via `create()`) | the normal case — almost always this one |

**`create()` alone never deletes anything, on purpose.** Calling it doesn't
even look at what's in the database — it only tracks which `Data` it has
already inserted *in this builder instance*. This is what makes it safe to
register more `Data` after an `apply()` and call `create()` again on its
own: only the newly registered rows go in, nothing already there gets
touched, and nothing gets deleted first.

```python
builder.new_publisher()
builder.apply()          # deletes leftovers, inserts the publisher

book = builder.new_book_for_current_publisher()
builder.create()         # NOT apply() — inserts only the new book,
                          # doesn't re-delete/re-insert the publisher
```

**`apply()` is safe to call more than once on the same builder**, and this
is the normal way to reuse one builder across several independent
scenarios in the same test module: seed scenario 1, `apply()`, assert; seed
scenario 2 (fresh `Data`, same builder instance), `apply()` again —
`delete()` clears scenario 1's rows first (rows already marked inserted by
the earlier `create()` are left alone by `create()` itself, but still get
deleted by `delete()`, since `delete()` doesn't care about that flag), then
`create()` inserts only scenario 2's rows. The two scenarios never coexist
in the database, and scenario 2 never has to know what scenario 1 seeded.

## Template patterns

Beyond the base template (`new_publisher()`) and the "for current" shortcut
(`new_book_for_current_publisher()`) above:

- **Cluster template** — creates several related rows in one call, returning
  a dataclass holding every one of them:
  ```python
  from dataclasses import dataclass

  @dataclass(frozen=True)
  class OrderWithItem:
      order: Data
      item: Data

  def new_order_with_item(self) -> OrderWithItem:
      order = self.new_order_for_current_customer()
      item = self.new_order_item_for_current_order()
      return OrderWithItem(order, item)
  ```
- **Partial template** — fills one recurring group of columns on an
  already-created row:
  ```python
  def set_customer_as_loyal(self, customer: Data) -> Data:
      return customer.set_column(CustomerColumn.LOYALTY_POINTS, 1000)
  ```
- **Parameterized template** — takes the values that vary often enough to be
  worth naming, instead of every call site chaining `set_column()`:
  ```python
  def new_book(self, title: str, price: str) -> Data:
      return self.new_book_for_current_publisher().set_column(BookColumn.TITLE, title).set_column(
          BookColumn.PRICE, Decimal(price)
      )
  ```
  Prefer a plain `str`/`int` parameter over asking the caller to build a
  `Decimal`/`timedelta`/etc. themselves — do that conversion once, inside
  the template.

## Naming: seeding more than one thing at once

`with_name(name)` scopes subsequent registrations to a name (default
`"root"`) — useful when a test seeds two independent sets of data (e.g. two
customers, each with their own order) and needs to look each set up
separately afterward:

```python
builder.new_customer()          # under "root"
builder.with_name("second")
builder.new_customer()          # under "second"

builder.get_data(MyTable.CUSTOMER, "root")   # the first one
builder.get_data(MyTable.CUSTOMER, "second") # the second one
builder.get_data(MyTable.CUSTOMER)           # same as passing the current name
```

## Raw SQL for a column that needs it

Most columns bind a plain value. Some need a SQL expression instead — a
PostGIS point, a `CAST`, an enum type coercion:

```python
warehouse = builder.new_warehouse().set_column(
    WarehouseColumn.CODE, SqlExpression("UPPER(?)", "wh-1")
)
```

`sql` is inlined in place of that column's placeholder; `params` are bound
in its place — everything else about the row is unaffected.

## A table your templates never seed

Some tables are written by the application itself as a side effect of the
flow under test (an audit log, a usage-tracking table) — nothing ever calls
a template for them, so `delete()` doesn't know to clear them by default.
Mark them explicitly, and call it *last* so it's cleaned up *first*:

```python
def delete(self) -> None:
    self._delete_table(MyTable.USAGE_LOG)  # written by the app, never seeded
    super().delete()
```

## Converting a project-specific value type

`Data.set_column` only ever stores what you hand it. If your project has its
own date-builder/money/whatever type that needs converting before it hits
the database, override `set_data_column` and tag the relevant columns with a
`target_type`:

```python
class OrderColumn(TestColumn, Enum):
    PLACED_AT = "placed_at"

    @property
    def sql_name(self) -> str:
        return self.value

    @property
    def target_type(self) -> TargetType:
        if self is OrderColumn.PLACED_AT:
            return TargetType.TIMESTAMP
        return TargetType.TRANSPARENT


def set_data_column(self, data: Data, column: TestColumn, value: Any) -> Data:
    if isinstance(value, MyDate) and column.target_type is TargetType.TIMESTAMP:
        return data.set_column(column, value.to_datetime())
    return super().set_data_column(data, column, value)
```

## Reading back state your builder didn't write

`self.engine` gives direct access to the SQLAlchemy `Engine` behind the
builder — for read-back assertions (`SELECT` a column the application under
test mutated) or one-off queries that don't fit the row-templating model.
Wrap the ones you use often in a named method on your builder
(`current_order_status(order)`) rather than inlining SQL at every call
site — it reads better and survives a column rename in one place.

Don't reach for the builder to *simulate the application itself* writing a
row (e.g. inserting into that audit-log table `_delete_table` cleans up) —
that's usually clearer left as plain SQL directly in the test, with a
comment saying so, since it isn't seeding: it's standing in for the app.

## Database support

**PostgreSQL only, for now.** The `DatabaseVendor` enum keeps the same four
members as the Java original (`POSTGRESQL`, `MARIADB`, `MYSQL`, `ORACLE`)
for shape parity, but `TestDataBuilder._resolve_generated_id` only
implements `POSTGRESQL` — the others raise `NotImplementedError`. Adding a
vendor means implementing its generated-id read-back there (see that
method's docstring for what differs — `RETURNING` support, out-bind
variables, cursor `lastrowid` — by vendor and DBAPI driver) and adding a
schema + test suite for it, mirroring `tests/resources/bookstore-schema-postgres.sql`
and `tests/test_*_behavior.py`.

```python
MyTestDataBuilder(engine, DatabaseVendor.POSTGRESQL)  # works
MyTestDataBuilder(engine, DatabaseVendor.MYSQL)       # raises NotImplementedError, only on create()/apply()
```

### Running your tests against a real database

TestDataBuilder only ever needs a SQLAlchemy `Engine` — how you stand up
the database behind it is entirely up to you. This library's own test suite
uses [testcontainers-python](https://testcontainers-python.readthedocs.io/)'s
`PostgresContainer`:

```python
# this library's own tests/conftest.py, as a concrete example
import pytest
from sqlalchemy import create_engine, text
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_engine():
    with PostgresContainer("postgres:16-alpine") as postgres:
        engine = create_engine(postgres.get_connection_url())
        with engine.begin() as connection:
            for statement in SCHEMA_PATH.read_text().split(";"):
                if statement.strip():
                    connection.execute(text(statement))
        yield engine
        engine.dispose()


@pytest.fixture
def builder(postgres_engine):
    builder = BookstoreTestDataBuilder(postgres_engine, DatabaseVendor.POSTGRESQL)
    yield builder
    # truncate all tables here — see tests/conftest.py for why this, and not
    # just builder.delete(), is needed for cross-test isolation with a
    # session-scoped container and a fresh builder instance per test
```

A fresh `TestDataBuilder` instance per test only knows about the tables *it*
touches, so a session-scoped container needs an explicit
`TRUNCATE ... RESTART IDENTITY CASCADE` in the fixture teardown for full
isolation between tests — `builder.delete()` alone isn't enough once the
builder itself is recreated per test. See `tests/conftest.py` in this repo.

## For Claude Code users

**Using this library from another project?** Copy this repo's
`src/claude/test-data-builder-usage/` into your own project's
`.claude/skills/` — the condensed "what to write in your project" version
of this guide (install, mapping your schema to `TestTable`/`TestColumn`/`Data`).
It lives outside `.claude/skills/` here since it's not meant to auto-load
while working on this repo's own code — see the README's "For Claude Code
users" section for why and how to copy it.

**Working on this repo's own code?** This repo's own
`.claude/skills/test-data-builder-library/` skill covers decisions specific
to *maintaining this codebase* (Postgres-only scope, the bookstore example,
API conventions) — load it only when changing the library itself, not when
consuming it.

## Contributing

See the [README](README.md#contributing).
