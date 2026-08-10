from enum import Enum

from testdatabuilder.generic import TestColumn


class PublisherColumn(TestColumn, Enum):
    ID = "id"
    NAME = "name"
    COUNTRY = "country"

    @property
    def sql_name(self) -> str:
        return self.value
