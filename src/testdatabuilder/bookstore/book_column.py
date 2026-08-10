from enum import Enum

from testdatabuilder.generic import TestColumn


class BookColumn(TestColumn, Enum):
    ID = "id"
    TITLE = "title"
    ISBN = "isbn"
    PRICE = "price"
    PUBLISHER_ID = "publisher_id"

    @property
    def sql_name(self) -> str:
        return self.value
