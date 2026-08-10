from enum import Enum

from testdatabuilder.generic import TestColumn


class OrderEventColumn(TestColumn, Enum):
    """Columns of order_event, a table written by application code as a side
    effect of processing an order — never seeded by a template. Used to
    demonstrate TestDataBuilder._delete_table.
    """

    ID = "id"
    ORDER_ID = "order_id"
    EVENT_TYPE = "event_type"
    OCCURRED_AT = "occurred_at"

    @property
    def sql_name(self) -> str:
        return self.value
