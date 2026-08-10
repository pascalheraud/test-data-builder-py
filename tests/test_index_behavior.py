"""Per-table index/distinct-defaults behavior, ported from IndexBehavior.java."""

from testdatabuilder.bookstore import BookColumn


def test_two_calls_to_the_same_base_template_produce_distinct_index_derived_defaults(builder):
    # Given a publisher and two books created for it via the same base template
    publisher = builder.new_publisher()
    first = builder.new_book_for_current_publisher()
    second = builder.new_book_for_current_publisher()

    # Then each call got a distinct, table-scoped index
    first_isbn = first.get_column(BookColumn.ISBN)
    second_isbn = second.get_column(BookColumn.ISBN)
    assert first_isbn != second_isbn
    assert publisher.index == 0
    assert first.index == 0
    assert second.index == 1

    # When applying them
    # Then there is no unique-constraint violation on the isbn column
    builder.apply()


def test_index_is_scoped_per_table_independently(builder):
    # Given two publishers already created (index 0 and 1)
    builder.new_publisher()
    builder.new_publisher()

    # When creating the first warehouse
    warehouse = builder.new_warehouse()

    # Then its index starts back at 0 — indexing is per table, not global
    assert warehouse.index == 0


def test_repeated_customer_and_warehouse_templates_never_collide_on_unique_columns(builder):
    # Given several customers and warehouses created via the same base templates
    builder.new_customer()
    builder.new_customer()
    builder.new_customer()
    builder.new_warehouse()
    builder.new_warehouse()

    # When applying them
    # Then there is no unique-constraint violation on any of their unique columns
    builder.apply()
