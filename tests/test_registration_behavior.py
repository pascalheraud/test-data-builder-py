"""Registration/naming behavior of TestDataBuilder, ported from RegistrationBehavior.java."""

import pytest
from testdatabuilder.bookstore import BookstoreTable


def test_registered_data_is_retrievable_by_name_and_table(builder):
    # Given a publisher registered under the default name
    publisher = builder.new_publisher()

    # When looking it up by name and table
    found = builder.get_data(BookstoreTable.PUBLISHER, "root")
    found_list = builder.get_data_list(BookstoreTable.PUBLISHER, "root")

    # Then it is retrievable, alone or in the full list for that table
    assert found is publisher
    assert found_list == [publisher]


def test_with_name_scopes_subsequent_registrations(builder):
    # Given a publisher under the default name, then one under a different name
    first = builder.new_publisher()
    builder.with_name("second-scenario")
    second = builder.new_publisher()

    # When looking each up by its own name
    found_under_root = builder.get_data(BookstoreTable.PUBLISHER, "root")
    found_under_second_scenario = builder.get_data(BookstoreTable.PUBLISHER, "second-scenario")

    # Then each name resolves only to its own publisher
    assert found_under_root is first
    assert found_under_second_scenario is second

    # When switching back to the default name and registering another
    builder.with_name("root")
    third = builder.new_publisher()
    root_list = builder.get_data_list(BookstoreTable.PUBLISHER, "root")

    # Then the default name's list now holds both of its publishers, not the other name's
    assert root_list == [first, third]


def test_get_data_throws_when_zero_or_more_than_one_match(builder):
    # Given no publisher registered yet
    # When/Then looking one up raises
    with pytest.raises(ValueError):
        builder.get_data(BookstoreTable.PUBLISHER, "root")

    # Given two publishers registered under the same name
    builder.new_publisher()
    builder.new_publisher()

    # When/Then looking up "the" publisher for that name also raises — there isn't exactly one
    with pytest.raises(ValueError):
        builder.get_data(BookstoreTable.PUBLISHER, "root")


def test_current_throws_until_something_is_registered_then_returns_the_latest(builder):
    # Given no publisher registered yet
    # When/Then a template relying on "current" raises
    with pytest.raises(ValueError):
        builder.new_book_for_current_publisher()

    # Given two publishers registered, the second one most recently
    builder.new_publisher()
    second_publisher = builder.new_publisher()

    # When a book is created "for current"
    from testdatabuilder.bookstore import BookColumn

    book = builder.new_book_for_current_publisher()
    linked_publisher = book.get_column(BookColumn.PUBLISHER_ID)

    # Then it links to the most recently created publisher, not the first one
    assert linked_publisher is second_publisher
