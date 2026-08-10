from enum import Enum, auto


class TargetType(Enum):
    """The kind of column a TestColumn maps to, for value conversion in
    TestDataBuilder.set_data_column."""

    TRANSPARENT = auto()
    """No conversion needed — the default, see TestColumn.target_type."""
    STRING = auto()
    """The column expects a str."""
    DATE = auto()
    """The column expects a date (no time component)."""
    TIMESTAMP = auto()
    """The column expects a datetime."""


class TestColumn:
    """A column usable by Data.set_column/Data.get_column, as a typo-safe
    alternative to a raw string key. Implemented as a mixin on a
    project-specific enum, one member per column of a table (mirrors
    TestTable) — e.g. `class BookColumn(TestColumn, Enum): TITLE = "title"`.
    Plain base class rather than an ABC: Python's `EnumMeta` and `ABCMeta`
    don't compose, and every table/column enum needs to mix this in
    alongside `Enum`.
    """

    @property
    def sql_name(self) -> str:
        """The SQL column name."""
        raise NotImplementedError

    @property
    def target_type(self) -> TargetType:
        """The target type this column converts values to, for
        TestDataBuilder.set_data_column. Defaults to TRANSPARENT — a column
        enum overrides this only when it needs one."""
        return TargetType.TRANSPARENT
