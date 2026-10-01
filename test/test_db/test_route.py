"""Tests for Route identity keyed by room (single route per room)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from menuflow.db.route import Route, RouteState

BOT_A = "@botA:example.com"
BOT_B = "@botB:example.com"
ROOM_PK = 1


def _make_row(
    *,
    route_id: int = 10,
    room: int = ROOM_PK,
    client: str = BOT_A,
    node_id: str = "start",
    state: str = "start",
    variables: dict | None = None,
    stack: str = "{}",
) -> dict:
    return {
        "id": route_id,
        "room": room,
        "client": client,
        "node_id": node_id,
        "state": state,
        "variables": variables if variables is not None else {"route": {}},
        "stack": stack,
    }


@pytest.fixture
def mock_db(mocker):
    db = MagicMock()
    db.fetchrow = AsyncMock()
    db.execute = AsyncMock()
    mocker.patch.object(Route, "db", db)
    return db


@pytest.mark.asyncio
async def test_get_by_room_queries_by_room_only(mock_db):
    mock_db.fetchrow.return_value = _make_row()

    route = await Route.get_by_room(room=ROOM_PK, client=BOT_A)

    assert route is not None
    assert route.client == BOT_A
    call_args = mock_db.fetchrow.await_args
    assert "WHERE room=$1" in call_args.args[0]
    assert call_args.args[1:] == (ROOM_PK,)
    assert "client" not in call_args.args[0].lower().split("where")[1]
    mock_db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_by_room_reassigns_client_only_when_create(mock_db):
    mock_db.fetchrow.return_value = _make_row(client=BOT_A)

    route = await Route.get_by_room(room=ROOM_PK, client=BOT_B, create=True)

    assert route.client == BOT_B
    mock_db.execute.assert_awaited()
    update_sql = mock_db.execute.await_args.args[0]
    assert "UPDATE route SET client = $2" in update_sql
    assert "WHERE room = $1" in update_sql
    assert mock_db.execute.await_args.args[1] == ROOM_PK
    assert mock_db.execute.await_args.args[2] == BOT_B


@pytest.mark.asyncio
async def test_get_by_room_does_not_reassign_without_create(mock_db):
    mock_db.fetchrow.return_value = _make_row(client=BOT_A)

    route = await Route.get_by_room(room=ROOM_PK, client=BOT_B)

    assert route.client == BOT_A
    mock_db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_by_room_same_client_skips_update(mock_db):
    mock_db.fetchrow.return_value = _make_row(client=BOT_A)

    route = await Route.get_by_room(room=ROOM_PK, client=BOT_A, create=True)

    assert route.client == BOT_A
    mock_db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_by_room_create_false_returns_none(mock_db):
    mock_db.fetchrow.return_value = None

    route = await Route.get_by_room(room=ROOM_PK, client=BOT_A, create=False)

    assert route is None
    mock_db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_by_room_without_client_does_not_create(mock_db):
    mock_db.fetchrow.return_value = None

    route = await Route.get_by_room(room=ROOM_PK, create=True)

    assert route is None
    mock_db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_by_room_create_true_inserts(mock_db):
    mock_db.fetchrow.return_value = None

    route = await Route.get_by_room(room=ROOM_PK, client=BOT_A, create=True)

    assert route is not None
    assert route.client == BOT_A
    assert route.state == RouteState.START
    insert_sql = mock_db.execute.await_args.args[0]
    assert "INSERT INTO route" in insert_sql
    assert "ON CONFLICT" not in insert_sql
