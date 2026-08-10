"""delete()/with_delete_all()/apply() behavior, ported from DeleteBehavior.java."""

from datetime import datetime

from sqlalchemy import text


def test_delete_removes_child_rows_before_parent_rows(builder):
    # Given a publisher and a book referencing it, both created
    builder.new_publisher()
    builder.new_book_for_current_publisher()
    builder.create()

    # When deleting
    # book references publisher: deleting publisher first would violate the FK.
    # delete() must delete book (touched after publisher) before publisher.
    builder.delete()
    book_count = builder.count_books()
    publisher_count = builder.count_publishers()

    # Then both tables are empty
    assert book_count == 0
    assert publisher_count == 0


def test_delete_table_clears_a_table_nothing_seeded_without_violating_its_foreign_key(builder):
    # Given a customer and an order created, plus an order_event row written
    # directly — order_event is written by application code, never through
    # the builder, so insert it directly here as the application under test would.
    builder.new_customer()
    order = builder.new_order_for_current_customer()
    builder.create()
    with builder.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO order_event (order_id, event_type, occurred_at) "
                "VALUES (:order_id, :event_type, :occurred_at)"
            ),
            {"order_id": order.generated_id, "event_type": "CREATED", "occurred_at": datetime.now()},
        )

    # When deleting
    # BookstoreTestDataBuilder.delete() calls _delete_table(ORDER_EVENT) last, so it is
    # removed first — before the order it references.
    builder.delete()
    order_event_count = builder.count_order_events()
    order_count = builder.count_orders()
    customer_count = builder.count_customers()

    # Then every table, including the unseeded order_event, is empty
    assert order_event_count == 0
    assert order_count == 0
    assert customer_count == 0


def test_delete_alone_removes_rows_without_inserting_anything_new(builder):
    # Given a publisher already applied
    builder.new_publisher()
    builder.apply()

    # When calling delete() alone, with nothing new registered
    builder.delete()
    publisher_count = builder.count_publishers()

    # Then the table is empty — unlike apply(), delete() alone never inserts
    assert publisher_count == 0


def test_with_delete_all_replaces_the_tracked_tables_with_exactly_what_is_passed(builder):
    from testdatabuilder.bookstore import BookstoreTable

    # Given a publisher, a book, and a customer, all created
    builder.new_publisher()
    builder.new_book_for_current_publisher()
    builder.new_customer()
    builder.create()

    # When explicitly restricting cleanup to book/publisher — customer is left
    # alone even though the builder touched it
    builder.with_delete_all(BookstoreTable.BOOK, BookstoreTable.PUBLISHER)
    builder.delete()
    book_count = builder.count_books()
    publisher_count = builder.count_publishers()
    customer_count = builder.count_customers()

    # Then only book and publisher are cleared, customer still has its row
    assert book_count == 0
    assert publisher_count == 0
    assert customer_count == 1


def test_apply_clears_the_previous_batch_before_inserting_the_new_one(builder):
    # Given a first publisher/book pair applied
    builder.new_publisher()
    builder.new_book_for_current_publisher()
    builder.apply()
    publisher_count_after_first_apply = builder.count_publishers()
    book_count_after_first_apply = builder.count_books()
    assert publisher_count_after_first_apply == 1
    assert book_count_after_first_apply == 1

    # When a second "scenario" is seeded and applied, reusing the same builder instance
    builder.new_publisher()
    builder.new_book_for_current_publisher()
    builder.apply()
    publisher_count_after_second_apply = builder.count_publishers()
    book_count_after_second_apply = builder.count_books()

    # Then only the second scenario's rows remain — apply() cleared the first batch first
    assert publisher_count_after_second_apply == 1
    assert book_count_after_second_apply == 1
