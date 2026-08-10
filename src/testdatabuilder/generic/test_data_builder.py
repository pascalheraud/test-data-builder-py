from abc import ABC
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .data import Data
from .database_vendor import DatabaseVendor
from .sql_expression import SqlExpression
from .test_column import TargetType, TestColumn
from .test_table import TestTable

_DEFAULT_NAME = "root"


class TestDataBuilder(ABC):
    """Seeds a database with rows for repository or E2E tests, using raw SQL
    only — it never touches ORM model classes or repositories. Subclasses
    (one per project) add template methods (e.g. `new_book()`) that build a
    pre-filled Data and register it via `register`.

    Works identically whatever the source of `engine` (a Testcontainers
    engine for integration tests, or any other SQLAlchemy Engine) — the
    builder only ever depends on it.
    """

    def __init__(self, engine: Engine, vendor: DatabaseVendor) -> None:
        """
        :param engine: the database to seed rows into
        :param vendor: the database vendor `engine` connects to — drives how
            the generated id is read back after an INSERT, since the
            mechanism (and DBAPI driver) differs by vendor.
        """
        self._engine = engine
        self._vendor = vendor

        self._ordered_data: list[Data] = []
        self._to_delete_tables: list[TestTable] = []
        self._current_by_table: dict[TestTable, Data] = {}
        self._data_naming: dict[str, dict[TestTable, list[Data]]] = {}
        self._next_index_by_table: dict[TestTable, int] = {}

        self._name = _DEFAULT_NAME

    @property
    def engine(self) -> Engine:
        """Direct access to the underlying SQLAlchemy Engine, for
        queries/deletes outside the Data template mechanism — a
        project-specific subclass uses it for read-back helper methods
        (e.g. `last_mock_call_content`), and calling test code can use it
        directly too instead of standing up a second connection just to
        read back what `create` inserted.
        """
        return self._engine

    def set_data_column(self, data: Data, column: TestColumn, value: Any) -> Data:
        """Sets `column` on `data`, converting `value` first if needed. A
        `date`/`datetime` is converted per `column.target_type` — to a
        `date`, a `datetime`, or a `str` — since the DBAPI driver can't
        always infer the SQL type of an arbitrary date-like value. Any other
        value is stored as-is. A project-specific subclass overrides this to
        convert project-specific value types (e.g. a date-builder type) to a
        `date`/`datetime` and delegate to this implementation.
        """
        if isinstance(value, (date, datetime)):
            target = column.target_type
            if target is TargetType.TIMESTAMP:
                converted: Any = value if isinstance(value, datetime) else datetime(value.year, value.month, value.day)
            elif target is TargetType.DATE:
                converted = value.date() if isinstance(value, datetime) else value
            elif target is TargetType.STRING:
                converted = str(value)
            else:
                converted = value
            return data.set_column(column, converted)
        return data.set_column(column, value)

    def with_name(self, name: str) -> "TestDataBuilder":
        """Switches the current naming scope — subsequent `register`ed Data
        are filed under `name` until this is called again.
        """
        self._name = name
        return self

    def _register(self, data: Data) -> Data:
        """Registers a Data built by a template method, under the builder's
        current name. Any Data it references as a column value (for a
        foreign key) must already be registered — template methods create
        and register a parent before building a child that references it,
        so this never needs to insert one out of order.
        """
        self._ordered_data.append(data)
        self._current_by_table[data.table] = data
        self._data_naming.setdefault(self._name, {}).setdefault(data.table, []).append(data)
        return data

    def _delete_table(self, table: TestTable) -> None:
        """Marks `table` for cleanup on the next `delete()`, without
        registering any Data for it. For tables written as a side effect of
        the code under test rather than seeded by a template method (e.g. an
        audit/log table written by the app itself) — `delete()` otherwise
        only clears tables it has seen through `register`.

        Calling this again for a table already marked moves it back to the
        most-recently-touched position — needed for the same builder to be
        reused across several `apply()` calls while keeping this table
        deleted first every time, not just on the first call.
        """
        self._mark_touched(table)

    def _mark_touched(self, table: TestTable) -> None:
        """Moves `table` to the end of `_to_delete_tables` (the
        most-recently-touched position), even if it was already present —
        needed so `delete()`'s reverse-of-touch-order guarantee holds for a
        builder reused across several cycles.
        """
        if table in self._to_delete_tables:
            self._to_delete_tables.remove(table)
        self._to_delete_tables.append(table)

    def _next_index(self, table: TestTable) -> int:
        """Returns a fresh, table-scoped index (0, 1, 2, ...) on every call.
        Template methods use it to derive distinct default values (e.g.
        unique emails, incrementing numeric bases) so calling a template
        several times never produces colliding rows.
        """
        index = self._next_index_by_table.get(table, 0)
        self._next_index_by_table[table] = index + 1
        return index

    def _new_data(self, table: TestTable) -> Data:
        """A blank Data for `table`, tagged with a fresh table-scoped index
        (see `_next_index`) so the caller can derive distinct defaults from
        `Data.index` without computing the index separately. Base template
        methods (e.g. `new_client()`) start from this instead of
        `Data(table)` plus a separate `_next_index(table)` call.
        """
        return Data(table, self._next_index(table))

    def _current(self, table: TestTable) -> Data:
        """The most recently registered Data for the given table, across all
        names. Backs template methods like `new_contract_for_current_client()`.
        """
        data = self._current_by_table.get(table)
        if data is None:
            raise ValueError(f"No current data for table {table}")
        return data

    def get_data(self, table: TestTable, name: str | None = None) -> Data:
        """The single Data registered for `table` under `name` (the
        builder's current name if omitted, see `with_name`).
        """
        datas = self.get_data_list(table, name)
        if len(datas) != 1:
            resolved_name = self._name if name is None else name
            raise ValueError(
                f"Expected exactly one {table} named '{resolved_name}', found {len(datas)}"
            )
        return datas[0]

    def get_data_list(self, table: TestTable, name: str | None = None) -> list[Data]:
        """Every Data registered for `table` under `name` (the builder's
        current name if omitted, see `with_name`), in registration order.
        """
        resolved_name = self._name if name is None else name
        return self._data_naming.get(resolved_name, {}).get(table, [])

    def count_rows(self, table: TestTable) -> int:
        """Number of rows currently in `table` — e.g. to assert
        `delete()`/`apply()` actually cleared it.
        """
        with self._engine.connect() as connection:
            return connection.execute(
                text(f"SELECT COUNT(*) FROM {table.sql_name}")
            ).scalar_one()

    def apply(self) -> None:
        """`delete()` then `create()` — call once all Data have been
        declared.
        """
        self.delete()
        self.create()

    def delete(self) -> None:
        """Issues `DELETE FROM <table>;` for every table touched, in reverse
        touched order (children before parents) to respect foreign keys —
        see `_to_delete_tables`, populated by `_insert`, `_delete_table`, and
        `with_delete_all`.
        """
        with self._engine.begin() as connection:
            for table in reversed(self._to_delete_tables):
                connection.execute(text(f"DELETE FROM {table.sql_name}"))

    def with_delete_all(self, *tables: TestTable) -> "TestDataBuilder":
        """Replaces whatever was already marked for deletion with exactly
        `tables`, for tests that want a fully clean slate on the next
        `delete()`/`apply()` regardless of what this builder actually
        touched. Pass them in the order you want them deleted (children
        before parents, respecting every foreign key) — `delete()`'s usual
        reverse-of-touched-order pass is accounted for internally, so the
        order given here is the order they're actually deleted in.
        """
        self._to_delete_tables = list(reversed(tables))
        return self

    def create(self) -> None:
        """Inserts every registered Data not yet `is_added` in registration
        order, resolving FK references to already-inserted Data's generated
        id. Safe to call more than once: rows already inserted by an
        earlier `create()` call are skipped, so more Data can be registered
        and inserted afterward without re-inserting (or re-`delete()`ing)
        what's already there.
        """
        with self._engine.begin() as connection:
            for data in self._ordered_data:
                if not data.is_added:
                    self._insert(connection, data)

    def _insert(self, connection: Any, data: Data) -> None:
        """Inserts `data` and reads its generated id back, using the
        mechanism appropriate for `self._vendor` — the one vendor-specific
        extension point of the whole builder. Unlike a shared JDBC
        `RETURN_GENERATED_KEYS` API, Python DBAPI drivers differ enough
        between vendors (RETURNING support, out-bind variables, cursor
        `lastrowid`) that the statement itself, not just the key lookup,
        varies — still driven entirely by `self._vendor` rather than by
        subclassing.
        """
        columns: list[str] = []
        placeholders: list[str] = []
        params: dict[str, Any] = {}
        for i, (column, value) in enumerate(data.columns.items()):
            columns.append(column)
            if isinstance(value, SqlExpression):
                placeholders.append(value.sql)
                for j, param in enumerate(value.params):
                    key = f"p{i}_{j}"
                    placeholders[-1] = placeholders[-1].replace("?", f":{key}", 1)
                    params[key] = param
                continue
            if isinstance(value, Data):
                value = value.generated_id
            key = f"p{i}"
            placeholders.append(f":{key}")
            params[key] = value

        base_sql = (
            f"INSERT INTO {data.table.sql_name} ({', '.join(columns)}) "
            f"VALUES ({', '.join(placeholders)})"
        )
        generated_id = self._resolve_generated_id(connection, base_sql, params)

        data._set_generated_id(generated_id)
        data._mark_added()
        self._mark_touched(data.table)

    def _resolve_generated_id(self, connection: Any, base_sql: str, params: dict[str, Any]) -> int:
        if self._vendor is DatabaseVendor.POSTGRESQL:
            result = connection.execute(text(f"{base_sql} RETURNING id"), params)
            return result.scalar_one()
        raise NotImplementedError(
            f"{self._vendor} is not supported yet — only DatabaseVendor.POSTGRESQL is implemented so far."
        )
