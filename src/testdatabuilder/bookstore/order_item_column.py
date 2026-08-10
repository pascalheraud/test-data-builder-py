from enum import Enum

from testdatabuilder.generic import TestColumn


class OrderItemColumn(TestColumn, Enum):
    ID = "id"
    ORDER_ID = "order_id"
    BOOK_ID = "book_id"
    QUANTITY = "quantity"
    UNIT_PRICE = "unit_price"

    @property
    def sql_name(self) -> str:
        return self.value
