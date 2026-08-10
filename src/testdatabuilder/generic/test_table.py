from typing import Sequence

from .test_column import TestColumn


class TestTable:
    """A table usable by TestDataBuilder. Implemented as a mixin on a
    project-specific enum, one member per table — e.g.
    `class BookstoreTable(TestTable, Enum): BOOK = ("book", BookColumn)`.
    Plain base class rather than an ABC: Python's `EnumMeta` and `ABCMeta`
    don't compose, and every table enum needs to mix this in alongside
    `Enum`.
    """

    @property
    def sql_name(self) -> str:
        """The SQL table name."""
        raise NotImplementedError

    @property
    def columns(self) -> Sequence[TestColumn]:
        """The columns of this table, e.g. list(MyTableColumn)."""
        raise NotImplementedError
