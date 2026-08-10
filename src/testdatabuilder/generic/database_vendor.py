from enum import Enum, auto


class DatabaseVendor(Enum):
    """A database vendor TestDataBuilder knows how to read a generated key
    back from after an INSERT. Mirrors the vendor list of the Java original
    (kept to the same vendors NativSQL supports there), but only
    `POSTGRESQL` is actually implemented in this Python port so far —
    `TestDataBuilder._resolve_generated_id` raises `NotImplementedError`
    for the others. Extend it there (and add a vendor to this enum first if
    it's missing) when support for another vendor is needed.
    """

    POSTGRESQL = auto()
    """PostgreSQL — the generated key is read back via a RETURNING clause."""
    MARIADB = auto()
    """MariaDB — not implemented yet."""
    MYSQL = auto()
    """MySQL — not implemented yet."""
    ORACLE = auto()
    """Oracle — not implemented yet."""
