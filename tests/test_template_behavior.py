"""Exercises the whole BookstoreTestDataBuilder end to end, ported from TemplateBehavior.java."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import text
from testdatabuilder.bookstore import BookColumn, BookstoreDate, CustomerColumn, CustomerStatus, WarehouseColumn


def test_base_templates_insert_with_distinct_index_derived_defaults(builder):
    # Given a publisher, a customer and a warehouse created via their base templates
    publisher = builder.new_publisher()
    customer = builder.new_customer()
    warehouse = builder.new_warehouse()

    # When creating them
    builder.create()
    email = customer.get_column(CustomerColumn.EMAIL)
    warehouse_name = warehouse.get_column(WarehouseColumn.NAME)

    # Then each got the expected, distinct, index-derived defaults
    assert publisher.generated_id is not None
    assert email == "customer0@example.com"
    assert warehouse_name == "Warehouse 0"


def test_for_current_shortcut_links_to_the_last_created_row_of_that_table(builder):
    # Given two publishers, then a book created "for current"
    builder.new_publisher()
    second_publisher = builder.new_publisher()
    book = builder.new_book_for_current_publisher()

    # When creating them
    builder.create()
    publisher_id_on_book = builder.current_book_publisher_id(book)

    # Then the book links to the most recently created publisher, not the first one
    assert publisher_id_on_book == second_publisher.generated_id


def test_for_order_variant_adds_a_second_item_to_an_order_that_is_no_longer_current(builder):
    # Given a first order with an item, then a second customer/order that
    # makes the first order no longer "current"
    builder.new_customer()
    builder.new_publisher()
    builder.new_book_for_current_publisher()
    first_order = builder.new_order_with_item()
    builder.new_customer()
    builder.new_order_with_item()

    # When adding a second item explicitly to the first order
    second_item_on_first_order = builder.new_order_item_for_order(first_order.order)
    builder.create()
    order_id_on_second_item = builder.current_order_item_order_id(second_item_on_first_order)
    item_count_for_first_order = builder.count_order_items(first_order.order)

    # Then the new item is linked to the first order, which now has two items
    assert order_id_on_second_item == first_order.order.generated_id
    assert item_count_for_first_order == 2


def test_cluster_template_returns_every_data_it_created_with_resolvable_foreign_keys(builder):
    # Given a customer, a publisher and a book, then an order-with-item cluster
    builder.new_customer()
    builder.new_publisher()
    builder.new_book_for_current_publisher()
    order_with_item = builder.new_order_with_item()

    # When creating them
    builder.create()
    order_id_on_item = builder.current_order_item_order_id(order_with_item.item)

    # Then both the order and the item got a generated id, and the item resolves to that order
    assert order_with_item.order.generated_id is not None
    assert order_with_item.item.generated_id is not None
    assert order_id_on_item == order_with_item.order.generated_id


def test_partial_template_mutates_an_already_created_data_in_place(builder):
    # Given a customer, made loyal via the partial template
    customer = builder.new_customer()
    builder.set_customer_as_loyal(customer)

    # When creating it
    builder.create()
    status = builder.current_customer_status(customer)

    # Then its status is GOLD
    assert status == CustomerStatus.GOLD.name


def test_parameterized_template_overrides_only_the_given_columns(builder):
    # Given a publisher, then a book created via the parameterized template
    builder.new_publisher()
    book = builder.new_book("The Pragmatic Programmer", "39.90")

    # When creating it
    builder.create()
    title = book.get_column(BookColumn.TITLE)
    price = book.get_column(BookColumn.PRICE)
    isbn = book.get_column(BookColumn.ISBN)

    # Then the given title/price were used, and the rest kept its base-template default
    assert title == "The Pragmatic Programmer"
    assert price == Decimal("39.90")
    assert isbn is not None


def test_set_data_column_converts_a_project_specific_value_type_per_column_target_type(builder):
    # Given a customer, then an order placed at a caller-given BookstoreDate
    builder.new_customer()
    order = builder.new_order_for_current_customer(BookstoreDate(datetime(2030, 6, 15, 8, 30)))

    # When creating it
    builder.create()
    placed_at = builder.current_order_placed_at(order)

    # Then set_data_column converted the BookstoreDate to a datetime and stored it
    assert placed_at == datetime(2030, 6, 15, 8, 30)


def test_external_id_is_a_random_uuid_not_derived_from_the_index(builder):
    # Given two customers created via the base template
    first = builder.new_customer()
    second = builder.new_customer()
    first_external_id = first.get_column(CustomerColumn.EXTERNAL_ID)
    second_external_id = second.get_column(CustomerColumn.EXTERNAL_ID)

    # Then each got its own random, valid UUID — not one derived from the index
    assert first_external_id is not None
    assert first_external_id != second_external_id
    uuid.UUID(first_external_id)


def test_current_order_status_reads_back_state_mutated_outside_the_builder(builder):
    # Given a customer and an order, created
    builder.new_customer()
    order = builder.new_order_for_current_customer()
    builder.create()

    # When the application under test changes the order's status —
    # updated directly here, not through the builder, on purpose
    with builder.engine.begin() as connection:
        connection.execute(
            text("UPDATE orders SET status = :status WHERE id = :id"),
            {"status": "SHIPPED", "id": order.generated_id},
        )
    status = builder.current_order_status(order)

    # Then the read-back helper reflects the mutated state
    assert status == "SHIPPED"


def test_full_scenario_applies_twice_without_leftover_rows_or_foreign_key_errors(builder):
    # Given a full first scenario (publisher, book, customer, order-with-item,
    # warehouse) applied, plus an order_event row written directly — order_event
    # is written by application code, never through the builder, so insert it
    # directly here as the application under test would
    builder.new_publisher()
    builder.new_book_for_current_publisher()
    builder.new_customer()
    order_with_item = builder.new_order_with_item()
    builder.new_warehouse()
    builder.apply()
    with builder.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO order_event (order_id, event_type, occurred_at) "
                "VALUES (:order_id, :event_type, :occurred_at)"
            ),
            {"order_id": order_with_item.order.generated_id, "event_type": "CREATED", "occurred_at": datetime.now()},
        )

    # When a second scenario is seeded under a different name and applied,
    # reusing the same builder instance
    builder.with_name("second-scenario")
    builder.new_publisher()
    builder.new_book_for_current_publisher()
    builder.new_customer()
    builder.new_order_with_item()
    builder.new_warehouse()
    builder.apply()

    # Then the first scenario's rows — including the unseeded order_event —
    # are gone, leaving only the second scenario's
    order_event_count = builder.count_order_events()
    order_count = builder.count_orders()
    publisher_count = builder.count_publishers()
    assert order_event_count == 0
    assert order_count == 1
    assert publisher_count == 1
