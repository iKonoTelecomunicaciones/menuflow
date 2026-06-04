"""Tests for Room cache propagation across bot_mxids for room-scoped variables."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from pytest_mock import MockerFixture

from menuflow.config import Config
from menuflow.db import Route
from menuflow.room import Room
from menuflow.utils.types import Scopes

SYNCED_PREFIX = [Scopes.ROOM.value]
NOT_SYNCED = [Scopes.ROUTE.value, Scopes.NODE.value]


@pytest_asyncio.fixture
async def second_room(mocker: MockerFixture, config: Config, room: Room) -> Room:
    mocker.patch.object(Route, "update")
    other_route = Route(room=1, node_id="start", client="@bar:foo.com")
    other = Room(room_id=room.room_id)
    other.matrix_client = MagicMock()
    other.bot_mxid = "@bar:foo.com"
    other.route = other_route
    other.config = config
    return other


@pytest_asyncio.fixture
async def other_room(mocker: MockerFixture, config: Config) -> Room:
    mocker.patch.object(Route, "update")
    other_route = Route(room=2, node_id="start", client="@foo:foo.com")
    other = Room(room_id="!other:foo.com")
    other.matrix_client = MagicMock()
    other.bot_mxid = "@foo:foo.com"
    other.route = other_route
    other.config = config
    return other


@pytest.fixture(autouse=True)
def _sync_cache_fixture(mocker: MockerFixture, room: Room, second_room: Room, other_room: Room):
    Room.by_room_id.clear()
    room._add_to_cache(bot_mxid=room.bot_mxid)
    second_room._add_to_cache(bot_mxid=second_room.bot_mxid)
    other_room._add_to_cache(bot_mxid=other_room.bot_mxid)
    yield
    Room.by_room_id.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", SYNCED_PREFIX)
async def test_set_variable_syncs_cache_for_room_scopes(
    room: Room, second_room: Room, other_room: Room, scope: str
):
    await room.set_variable(variable_id=f"{scope}.k", value="v")

    assert second_room.variables == room.variables
    assert not hasattr(second_room, "_vars_cache")
    assert second_room._variables[scope]["k"] == "v"

    assert other_room.variables == "{}"
    assert not hasattr(other_room, "_vars_cache") or other_room._variables == {}


@pytest.mark.asyncio
async def test_set_variable_syncs_cache_for_custom_scope_billing(
    room: Room, second_room: Room, other_room: Room
):
    """Custom scopes need explicit scope=...; billing.k alone resolves to route by default."""
    await room.set_variable(variable_id="k", value="v", scope="billing")

    assert second_room.variables == room.variables
    assert not hasattr(second_room, "_vars_cache")
    assert second_room._variables["billing"]["k"] == "v"

    assert other_room.variables == "{}"
    assert not hasattr(other_room, "_vars_cache") or other_room._variables == {}
