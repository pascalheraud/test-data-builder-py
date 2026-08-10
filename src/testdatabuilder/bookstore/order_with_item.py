from dataclasses import dataclass

from testdatabuilder.generic import Data


@dataclass(frozen=True)
class OrderWithItem:
    """Every Data created by BookstoreTestDataBuilder.new_order_with_item()."""

    order: Data
    item: Data
