"""Compatibility contracts for asyncpg (no live Postgres)."""

from __future__ import annotations

import inspect
import sys

import asyncpg
from asyncpg import Connection, Record
from mautrix.util.async_db import Database

from menuflow.db.migrations import upgrade_table


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


def test_create_pool_and_database_create_accept_menuflow_db_args():
    """Menuflow passes menuflow.database_opts into Database.create(db_args=...).

    asyncpg 0.32 changed min_size semantics and added init_size; keep asserting
    the kwargs Menuflow/mautrix historically forward still bind.
    """
    pool_sig = inspect.signature(asyncpg.create_pool)
    assert "min_size" in pool_sig.parameters
    assert "max_size" in pool_sig.parameters
    # bind_partial fails if a required positional is missing; kwargs must be accepted.
    pool_sig.bind_partial(dsn="postgresql://localhost/menuflow", min_size=1, max_size=10)

    db_sig = inspect.signature(Database.create)
    for name in ("url", "upgrade_table", "db_args", "log"):
        assert name in db_sig.parameters
    db_sig.bind_partial(
        url="postgresql://localhost/menuflow",
        upgrade_table=upgrade_table,
        db_args={"min_size": 1, "max_size": 10},
    )
