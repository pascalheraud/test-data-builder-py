from enum import Enum

from testdatabuilder.generic import TestColumn


class CustomerColumn(TestColumn, Enum):
    ID = "id"
    EMAIL = "email"
    FULL_NAME = "full_name"
    LOYALTY_POINTS = "loyalty_points"
    STATUS = "status"
    EXTERNAL_ID = "external_id"

    @property
    def sql_name(self) -> str:
        return self.value
