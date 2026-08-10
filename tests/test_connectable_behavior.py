"""TestDataBuilder accepting a Connection/Session in addition to an Engine —
the builder must never commit/rollback on its own in that case, so a
caller-driven rollback undoes everything the builder inserted."""

from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker
from testdatabuilder.bookstore import BookstoreTestDataBuilder
from testdatabuilder.generic import DatabaseVendor


def test_connection_mode_rows_are_visible_before_commit(postgres_engine: Engine):
    with postgres_engine.connect() as connection:
        connection.begin()
        builder = BookstoreTestDataBuilder(connection, DatabaseVendor.POSTGRESQL)

        builder.new_publisher()
        builder.create()

        # Visible on the same connection, before any commit
        assert connection.execute(text("SELECT COUNT(*) FROM publisher")).scalar_one() == 1
        connection.rollback()


def test_connection_mode_rollback_removes_everything_the_builder_inserted(postgres_engine: Engine):
    with postgres_engine.connect() as outer_connection:
        outer_connection.begin()
        builder = BookstoreTestDataBuilder(outer_connection, DatabaseVendor.POSTGRESQL)

        builder.new_publisher()
        builder.create()
        outer_connection.rollback()

    # A fresh connection only sees committed data — nothing survived the rollback
    with postgres_engine.connect() as verification_connection:
        assert verification_connection.execute(text("SELECT COUNT(*) FROM publisher")).scalar_one() == 0


def test_connection_mode_engine_property_resolves_to_the_underlying_engine(postgres_engine: Engine):
    with postgres_engine.connect() as connection:
        builder = BookstoreTestDataBuilder(connection, DatabaseVendor.POSTGRESQL)
        assert builder.engine is postgres_engine


def test_session_mode_rows_are_visible_before_commit(postgres_engine: Engine):
    session_factory = sessionmaker(bind=postgres_engine)
    session = session_factory()
    try:
        builder = BookstoreTestDataBuilder(session, DatabaseVendor.POSTGRESQL)

        builder.new_publisher()
        builder.create()

        assert session.execute(text("SELECT COUNT(*) FROM publisher")).scalar_one() == 1
        session.rollback()
    finally:
        session.close()


def test_session_mode_rollback_removes_everything_the_builder_inserted(postgres_engine: Engine):
    session_factory = sessionmaker(bind=postgres_engine)
    session = session_factory()
    try:
        builder = BookstoreTestDataBuilder(session, DatabaseVendor.POSTGRESQL)
        builder.new_publisher()
        builder.create()
        session.rollback()
    finally:
        session.close()

    with postgres_engine.connect() as verification_connection:
        assert verification_connection.execute(text("SELECT COUNT(*) FROM publisher")).scalar_one() == 0


def test_session_mode_engine_property_resolves_to_the_underlying_engine(postgres_engine: Engine):
    session_factory = sessionmaker(bind=postgres_engine)
    session = session_factory()
    try:
        builder = BookstoreTestDataBuilder(session, DatabaseVendor.POSTGRESQL)
        assert builder.engine is postgres_engine
    finally:
        session.close()


def test_engine_mode_still_commits_on_its_own(postgres_engine: Engine):
    # Regression check: Engine mode is unchanged from v1.0 — create() commits
    # by itself, no caller-managed transaction involved.
    builder = BookstoreTestDataBuilder(postgres_engine, DatabaseVendor.POSTGRESQL)
    builder.new_publisher()
    builder.create()

    with postgres_engine.connect() as verification_connection:
        assert verification_connection.execute(text("SELECT COUNT(*) FROM publisher")).scalar_one() == 1

    with postgres_engine.begin() as cleanup_connection:
        cleanup_connection.execute(text("TRUNCATE publisher RESTART IDENTITY CASCADE"))
