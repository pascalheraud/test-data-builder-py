from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SqlExpression:
    """A column value that must be inserted as a raw SQL expression instead
    of a plain bind parameter — e.g. `ST_GeomFromText(?, 4326)` for a PostGIS
    geometry column. `sql` is inlined into the INSERT statement in place of
    the column's placeholder; `params` are bound in its place, in order.
    """

    sql: str
    params: tuple[Any, ...] = field(default_factory=tuple)

    def __init__(self, sql: str, *params: Any) -> None:
        object.__setattr__(self, "sql", sql)
        object.__setattr__(self, "params", params)
