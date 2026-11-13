"""Compatibility contracts for asyncpg (no live Postgres)."""

from __future__ import annotations

import sys

import asyncpg
from asyncpg import Connection, Record


def test_record_and_connection_importable():
    assert Record is not None
    assert Connection is not None


def test_connection_query_methods_exist():
    for method_name in ("execute", "fetch", "fetchrow", "fetchval"):
        assert callable(getattr(Connection, method_name))


def test_asyncpg_import_matches_running_python():
    """Fail loudly when the installed wheel cannot load on this Python.

    asyncpg 0.29.0 historically lacked cp313 wheels; a successful import of
    Connection/Record already proves the binary extension loaded.
    """
    assert asyncpg.__version__
    assert sys.version_info >= (3, 10)
    # Touch the C extension surface used via mautrix.util.async_db.
    assert hasattr(asyncpg, "connect")
