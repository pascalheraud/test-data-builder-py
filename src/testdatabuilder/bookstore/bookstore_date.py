from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BookstoreDate:
    """A tiny stand-in for a real project's own date-builder value type —
    exists only to demonstrate BookstoreTestDataBuilder.set_data_column
    converting a project-specific value type based on a column's
    TestColumn.target_type, the same pattern a consumer uses for its own
    domain types (dates, money, whatever the generic Data.set_column
    shouldn't need to know about).
    """

    value: datetime
