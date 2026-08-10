"""create() behavior, ported from CreateBehavior.java."""


def test_create_inserts_every_registered_row_and_assigns_a_generated_id(builder):
    # Given a publisher and a book registered but not yet inserted
    publisher = builder.new_publisher()
    book = builder.new_book_for_current_publisher()

    # When creating them
    builder.create()

    # Then both rows are inserted and carry a generated id
    assert publisher.generated_id is not None
    assert book.generated_id is not None
    assert publisher.is_added
    assert book.is_added


def test_a_referenced_data_is_resolved_to_its_generated_id_only_after_it_is_itself_inserted(builder):
    # Given a publisher and a book referencing it
    publisher = builder.new_publisher()
    book = builder.new_book_for_current_publisher()

    # When creating them
    builder.create()
    publisher_id_on_book = builder.current_book_publisher_id(book)

    # Then the book's foreign key resolved to the publisher's generated id
    assert publisher_id_on_book == publisher.generated_id


def test_create_called_twice_only_inserts_newly_registered_data(builder):
    # Given a first publisher already created
    first_publisher = builder.new_publisher()
    builder.create()
    first_generated_id = first_publisher.generated_id

    # When registering a second publisher and calling create() again
    second_publisher = builder.new_publisher()
    builder.create()
    publisher_count = builder.count_publishers()

    # Then the first publisher is untouched and only the second one was inserted
    assert first_publisher.generated_id == first_generated_id
    assert second_publisher.generated_id is not None
    assert second_publisher.generated_id != first_generated_id
    assert publisher_count == 2
