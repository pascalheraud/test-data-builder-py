import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from testdatabuilder.generic import (
    Data,
    DatabaseVendor,
    SqlExpression,
    TargetType,
    TestColumn,
    TestDataBuilder,
)

from .book_column import BookColumn
from .bookstore_date import BookstoreDate
from .bookstore_table import BookstoreTable
from .customer_column import CustomerColumn
from .customer_status import CustomerStatus
from .order_column import OrderColumn
from .order_item_column import OrderItemColumn
from .order_with_item import OrderWithItem
from .publisher_column import PublisherColumn
from .warehouse_column import WarehouseColumn

_BASE_ORDER_DATE = datetime(2024, 1, 1, 10, 0)


class BookstoreTestDataBuilder(TestDataBuilder):
    """Example project-specific builder for the bookstore demo domain.
    Exercises every template pattern documented for TestDataBuilder: a base
    template, a "for current" shortcut, a cluster template, a partial
    template, a parameterized template, an SqlExpression column, a
    `_delete_table` override for a table nothing seeds, a `set_data_column`
    override converting a project-specific value type (BookstoreDate) per
    column `target_type`, and an `engine`-backed read-back helper
    (`current_order_status`) for state outside the Data mechanism.

    One instance is built per vendor in this library's own test suite —
    same class, only the DatabaseVendor passed to the constructor changes.
    """

    def __init__(self, engine: Engine, vendor: DatabaseVendor) -> None:
        super().__init__(engine, vendor)

    def set_data_column(self, data: Data, column: TestColumn, value: Any) -> Data:
        """Converts a BookstoreDate to a datetime for a TIMESTAMP-targeted
        column (see OrderColumn.PLACED_AT). Mirrors how a real project
        converts its own date-builder type — the generic Data.set_column
        never needs to know BookstoreDate exists.
        """
        if isinstance(value, BookstoreDate) and column.target_type is TargetType.TIMESTAMP:
            bookstore_date = value
            return data.set_column(column, bookstore_date.value)
        return super().set_data_column(data, column, value)

    # --- base templates ---

    def new_publisher(self) -> Data:
        publisher = self._new_data(BookstoreTable.PUBLISHER)
        index = publisher.index
        return self._register(
            publisher.set_column(PublisherColumn.NAME, f"Publisher {index}")
            .set_column(PublisherColumn.COUNTRY, "FR" if index % 2 == 0 else "US")
        )

    def new_customer(self) -> Data:
        customer = self._new_data(BookstoreTable.CUSTOMER)
        index = customer.index
        statuses = list(CustomerStatus)
        return self._register(
            customer.set_column(CustomerColumn.EMAIL, f"customer{index}@example.com")
            .set_column(CustomerColumn.FULL_NAME, f"Customer {index}")
            .set_column(CustomerColumn.LOYALTY_POINTS, 10 + index)
            .set_column(CustomerColumn.STATUS, statuses[index % len(statuses)].name)
            # UUID: a technical identifier, not derived from the index — see the skill's
            # "the one exception" rule. Stored as a string so it binds identically across
            # every supported vendor, rather than relying on a native UUID column type.
            .set_column(CustomerColumn.EXTERNAL_ID, str(uuid.uuid4()))
        )

    def new_warehouse(self) -> Data:
        warehouse = self._new_data(BookstoreTable.WAREHOUSE)
        index = warehouse.index
        return self._register(
            warehouse.set_column(WarehouseColumn.NAME, f"Warehouse {index}")
            .set_column(WarehouseColumn.CODE, SqlExpression("UPPER(?)", f"wh-{index}"))
            .set_column(WarehouseColumn.LATITUDE, Decimal("45.308556") + Decimal(index))
            .set_column(WarehouseColumn.LONGITUDE, Decimal("5.885139") + Decimal(index))
        )

    # --- "for current" shortcuts ---

    def new_book_for_current_publisher(self) -> Data:
        book = self._new_data(BookstoreTable.BOOK)
        index = book.index
        return self._register(
            book.set_column(BookColumn.TITLE, f"Book {index}")
            .set_column(BookColumn.ISBN, f"978-0-000-{index:06d}")
            .set_column(BookColumn.PRICE, Decimal("19.90") + Decimal(index))
            .set_column(BookColumn.PUBLISHER_ID, self._current(BookstoreTable.PUBLISHER))
        )

    def new_order_for_current_customer(self, placed_at: BookstoreDate | None = None) -> Data:
        """A new order for the current customer. `placed_at`, if given,
        overrides the base template's default — routed through
        `set_data_column` (not `Data.set_column` directly) so the
        BookstoreDate -> datetime conversion above actually runs.
        """
        order = self._new_data(BookstoreTable.ORDERS)
        index = order.index
        order = self._register(
            order.set_column(OrderColumn.CUSTOMER_ID, self._current(BookstoreTable.CUSTOMER))
            .set_column(OrderColumn.STATUS, "NEW")
            .set_column(OrderColumn.PLACED_AT, _BASE_ORDER_DATE + timedelta(days=index))
        )
        if placed_at is not None:
            order = self.set_data_column(order, OrderColumn.PLACED_AT, placed_at)
        return order

    def new_order_item_for_current_order(self) -> Data:
        return self.new_order_item_for_order(self._current(BookstoreTable.ORDERS))

    def new_order_item_for_order(self, order: Data) -> Data:
        """Same as `new_order_item_for_current_order()`, but for a specific
        order rather than the most recently created one — needed to add a
        second item to an order created earlier, once other templates (e.g.
        a second customer/order pair) have made it no longer "current".
        """
        item = self._new_data(BookstoreTable.ORDER_ITEM)
        index = item.index
        return self._register(
            item.set_column(OrderItemColumn.ORDER_ID, order)
            .set_column(OrderItemColumn.BOOK_ID, self._current(BookstoreTable.BOOK))
            .set_column(OrderItemColumn.QUANTITY, 1 + index % 5)
            .set_column(OrderItemColumn.UNIT_PRICE, Decimal("19.90"))
        )

    # --- cluster template ---

    def new_order_with_item(self) -> OrderWithItem:
        order = self.new_order_for_current_customer()
        item = self.new_order_item_for_current_order()
        return OrderWithItem(order, item)

    # --- partial template ---

    def set_customer_as_loyal(self, customer: Data) -> Data:
        return customer.set_column(CustomerColumn.LOYALTY_POINTS, 1000).set_column(
            CustomerColumn.STATUS, CustomerStatus.GOLD.name
        )

    # --- parameterized template ---

    def new_book(self, title: str, price: str) -> Data:
        """`price` is a plain str (e.g. "39.90") rather than a Decimal — the
        call site reads as a literal, and this one template is where the
        Decimal construction happens instead of being repeated at every
        call site.
        """
        return self.new_book_for_current_publisher().set_column(BookColumn.TITLE, title).set_column(
            BookColumn.PRICE, Decimal(price)
        )

    # --- order_event: written by application code, never seeded ---

    def delete(self) -> None:
        self._delete_table(BookstoreTable.ORDER_EVENT)
        super().delete()

    # --- read-back helpers, outside the Data template mechanism ---

    def current_order_status(self, order: Data) -> str:
        """orders.status, re-read after application code under test has
        updated it — `order` was seeded by this builder, but its status may
        have since changed as a side effect of the code under test, so the
        in-memory Data no longer reflects it. Uses `engine` directly, the
        same way a real project reads back mutated state.
        """
        with self.engine.connect() as connection:
            return connection.execute(
                text("SELECT status FROM orders WHERE id = :id"), {"id": order.generated_id}
            ).scalar_one()

    def current_book_publisher_id(self, book: Data) -> int:
        """book.publisher_id, re-read from the database rather than
        resolved off the in-memory Data."""
        with self.engine.connect() as connection:
            return connection.execute(
                text("SELECT publisher_id FROM book WHERE id = :id"), {"id": book.generated_id}
            ).scalar_one()

    def current_order_item_order_id(self, order_item: Data) -> int:
        """order_item.order_id, re-read from the database rather than
        resolved off the in-memory Data."""
        with self.engine.connect() as connection:
            return connection.execute(
                text("SELECT order_id FROM order_item WHERE id = :id"),
                {"id": order_item.generated_id},
            ).scalar_one()

    def count_order_items(self, order: Data) -> int:
        """Number of order_item rows for `order`."""
        with self.engine.connect() as connection:
            return connection.execute(
                text("SELECT COUNT(*) FROM order_item WHERE order_id = :id"),
                {"id": order.generated_id},
            ).scalar_one()

    def current_customer_status(self, customer: Data) -> str:
        """customer.status, re-read after the app under test has updated it."""
        with self.engine.connect() as connection:
            return connection.execute(
                text("SELECT status FROM customer WHERE id = :id"), {"id": customer.generated_id}
            ).scalar_one()

    def current_warehouse_code(self, warehouse: Data) -> str:
        """warehouse.code, re-read from the database — verifies what an
        SqlExpression column actually stored."""
        with self.engine.connect() as connection:
            return connection.execute(
                text("SELECT code FROM warehouse WHERE id = :id"), {"id": warehouse.generated_id}
            ).scalar_one()

    def current_order_placed_at(self, order: Data) -> datetime:
        """orders.placed_at, re-read from the database — verifies what
        `set_data_column` actually stored."""
        with self.engine.connect() as connection:
            return connection.execute(
                text("SELECT placed_at FROM orders WHERE id = :id"), {"id": order.generated_id}
            ).scalar_one()

    def count_publishers(self) -> int:
        """Number of publisher rows — e.g. to assert delete()/apply()
        actually cleared it."""
        return self.count_rows(BookstoreTable.PUBLISHER)

    def count_books(self) -> int:
        """Number of book rows."""
        return self.count_rows(BookstoreTable.BOOK)

    def count_customers(self) -> int:
        """Number of customer rows."""
        return self.count_rows(BookstoreTable.CUSTOMER)

    def count_orders(self) -> int:
        """Number of orders rows."""
        return self.count_rows(BookstoreTable.ORDERS)

    def count_warehouses(self) -> int:
        """Number of warehouse rows."""
        return self.count_rows(BookstoreTable.WAREHOUSE)

    def count_order_events(self) -> int:
        """Number of order_event rows — order_event is never seeded, only
        ever written directly (see delete())."""
        return self.count_rows(BookstoreTable.ORDER_EVENT)
