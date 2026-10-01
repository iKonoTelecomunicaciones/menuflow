"""Tests for deleting every stored record of a room."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from menuflow.db.room import Room as DBRoom
from menuflow.db.route import Route, RouteState
from menuflow.room import Room

ROOM_ID = "!room:example.com"
OTHER_ROOM_ID = "!other:example.com"
BOT = "@bot:example.com"


def _transaction_db() -> tuple[MagicMock, MagicMock]:
    """``acquire`` and ``transaction`` must be async context managers, not coroutines.

    ``@asynccontextmanager`` returns the manager on call; an ``AsyncMock`` would
    return a coroutine and break ``async with``.
    """
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.transaction.return_value = AsyncMock()
    db = MagicMock()

    @asynccontextmanager
    async def acquire():
        yield conn

    db.acquire = acquire
    return db, conn


@pytest.fixture
def purge_db(mocker):
    db, conn = _transaction_db()
    mocker.patch.object(DBRoom, "db", db)
    return conn


@pytest.fixture
def isolated_room_cache():
    saved = dict(Room.by_room_id)
    Room.by_room_id.clear()
    yield
    Room.by_room_id.clear()
    Room.by_room_id.update(saved)


@pytest.mark.asyncio
async def test_purge_deletes_webhook_route_and_room(purge_db):
    room = DBRoom(id=7, room_id=ROOM_ID)

    await room.purge()

    statements = [(call.args[0], call.args[1]) for call in purge_db.execute.await_args_list]
    assert statements == [
        ("DELETE FROM webhook WHERE room_id = $1", ROOM_ID),
        ("DELETE FROM route WHERE room = $1", 7),
        ("DELETE FROM room WHERE id = $1", 7),
    ]
    purge_db.transaction.assert_called_once()


@pytest.mark.asyncio
async def test_purge_does_not_touch_other_rooms(purge_db):
    target = DBRoom(id=7, room_id=ROOM_ID)
    other = DBRoom(id=8, room_id=OTHER_ROOM_ID)

    await target.purge()

    bound_values = [call.args[1] for call in purge_db.execute.await_args_list]
    assert other.id not in bound_values
    assert other.room_id not in bound_values
    assert all("WHERE" in call.args[0] for call in purge_db.execute.await_args_list)


@pytest.mark.asyncio
async def test_get_by_room_id_creates_empty_room_after_purge(mocker, isolated_room_cache):
    old = Room(room_id=ROOM_ID, id=1, variables='{"room": {"kept": true}}')
    old.purge = AsyncMock()
    Room.by_room_id[ROOM_ID] = old

    await old.purge()
    Room.remove_from_cache(ROOM_ID)
    assert ROOM_ID not in Room.by_room_id

    fresh = Room(room_id=ROOM_ID, id=99, variables="{}")
    mocker.patch.object(DBRoom, "get_by_room_id", AsyncMock(side_effect=[None, fresh]))
    mocker.patch.object(Room, "insert", AsyncMock())
    route = Route(
        room=99,
        client=BOT,
        node_id="start",
        state=RouteState.START,
        variables={"route": {}},
    )
    mocker.patch.object(Route, "get_by_room", AsyncMock(return_value=route))

    created = await Room.get_by_room_id(ROOM_ID, BOT, create=True)

    assert created is fresh
    assert created.id != old.id
    assert json.loads(created.variables) == {}
    assert created.route.state == RouteState.START
    assert created.route.node_id == "start"
    assert Room.by_room_id[ROOM_ID] is fresh
