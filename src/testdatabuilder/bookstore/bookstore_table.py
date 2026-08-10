from enum import Enum
from typing import Sequence

from testdatabuilder.generic import TestColumn, TestTable

from .book_column import BookColumn
from .customer_column import CustomerColumn
from .order_column import OrderColumn
from .order_event_column import OrderEventColumn
from .order_item_column import OrderItemColumn
from .publisher_column import PublisherColumn
from .warehouse_column import WarehouseColumn


class BookstoreTable(TestTable, Enum):
    """Tables of the bookstore example domain — a self-contained
    demonstration schema, unrelated to any consumer's own domain,
    exercising every template pattern documented for TestDataBuilder.
    """

    PUBLISHER = ("publisher", PublisherColumn)
    BOOK = ("book", BookColumn)
    CUSTOMER = ("customer", CustomerColumn)
    ORDERS = ("orders", OrderColumn)
    ORDER_ITEM = ("order_item", OrderItemColumn)
    WAREHOUSE = ("warehouse", WarehouseColumn)
    ORDER_EVENT = ("order_event", OrderEventColumn)

    def __init__(self, sql_name: str, column_enum: type[TestColumn]) -> None:
        self._sql_name = sql_name
        self._column_enum = column_enum

    @property
    def sql_name(self) -> str:
        return self._sql_name

    @property
    def columns(self) -> Sequence[TestColumn]:
        return list(self._column_enum)
