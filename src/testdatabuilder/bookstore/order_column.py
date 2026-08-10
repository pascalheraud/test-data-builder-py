from enum import Enum

from testdatabuilder.generic import TargetType, TestColumn


class OrderColumn(TestColumn, Enum):
    ID = "id"
    CUSTOMER_ID = "customer_id"
    STATUS = "status"
    # TIMESTAMP: BookstoreTestDataBuilder.set_data_column converts a BookstoreDate to
    # a datetime for this column — see new_order_for_current_customer(placed_at=...).
    PLACED_AT = "placed_at"

    @property
    def sql_name(self) -> str:
        return self.value

    @property
    def target_type(self) -> TargetType:
        if self is OrderColumn.PLACED_AT:
            return TargetType.TIMESTAMP
        return TargetType.TRANSPARENT
