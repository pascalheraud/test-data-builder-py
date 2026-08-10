from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from testcontainers.community.postgres import PostgresContainer
from testdatabuilder.bookstore import BookstoreTestDataBuilder
from testdatabuilder.generic import DatabaseVendor

_SCHEMA_PATH = Path(__file__).parent / "resources" / "bookstore-schema-postgres.sql"


@pytest.fixture(scope="session")
def postgres_engine() -> Engine:
    with PostgresContainer("postgres:16-alpine") as postgres:
        engine = create_engine(postgres.get_connection_url())
        with engine.begin() as connection:
            for statement in _SCHEMA_PATH.read_text().split(";"):
                if statement.strip():
                    connection.execute(text(statement))
        yield engine
        engine.dispose()


_ALL_TABLES = ("order_event", "order_item", "orders", "book", "warehouse", "customer", "publisher")


@pytest.fixture
def builder(postgres_engine: Engine) -> BookstoreTestDataBuilder:
    builder = BookstoreTestDataBuilder(postgres_engine, DatabaseVendor.POSTGRESQL)
    yield builder
    with postgres_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {', '.join(_ALL_TABLES)} RESTART IDENTITY CASCADE"))
