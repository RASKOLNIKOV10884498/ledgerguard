"""
LedgerGuard database connection management.

Loads the PostgreSQL connection string from .env
and manages a thread-safe PostgreSQL connection pool.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from psycopg2 import pool
from psycopg2.extensions import connection


# Load variables from .env
load_dotenv()


# Get PostgreSQL connection string
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not configured. "
        "Please add DATABASE_URL to your .env file."
    )


# PostgreSQL connection pool
_connection_pool: pool.ThreadedConnectionPool | None = None


def initialize_pool(
    min_connections: int = 1,
    max_connections: int = 10,
) -> None:
    """
    Create the PostgreSQL connection pool.
    """

    global _connection_pool

    if _connection_pool is not None:
        return

    if min_connections < 1:
        raise ValueError("min_connections must be at least 1.")

    if max_connections < min_connections:
        raise ValueError(
            "max_connections must be greater than or equal to "
            "min_connections."
        )

    _connection_pool = pool.ThreadedConnectionPool(
        min_connections,
        max_connections,
        dsn=DATABASE_URL,
    )


def get_connection() -> connection:
    """
    Get a PostgreSQL connection from the pool.
    """

    if _connection_pool is None:
        raise RuntimeError(
            "Database pool has not been initialized. "
            "Call initialize_pool() first."
        )

    return _connection_pool.getconn()


def release_connection(conn: connection) -> None:
    """
    Return a connection to the PostgreSQL connection pool.
    """

    if _connection_pool is None:
        raise RuntimeError(
            "Database pool has not been initialized."
        )

    _connection_pool.putconn(conn)


@contextmanager
def connection_context() -> Generator[connection, None, None]:
    """
    Safely borrow and return a database connection.

    Example:

        with connection_context() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
    """

    conn = get_connection()

    try:
        yield conn
    finally:
        release_connection(conn)


def close_pool() -> None:
    """
    Close all PostgreSQL connections.
    """

    global _connection_pool

    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None