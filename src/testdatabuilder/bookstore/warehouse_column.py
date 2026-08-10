from enum import Enum

from testdatabuilder.generic import TestColumn


class WarehouseColumn(TestColumn, Enum):
    ID = "id"
    NAME = "name"
    CODE = "code"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"

    @property
    def sql_name(self) -> str:
        return self.value
