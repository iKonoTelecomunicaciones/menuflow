"""Tests for Room cache keyed by room_id (single entry per room)."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from pytest_mock import MockerFixture

from menuflow.config import Config
from menuflow.db import Route
from menuflow.room import Room
from menuflow.utils.types import ProtectedVars, Scopes

PROTECTED_VAR = ProtectedVars.CUSTOMER_MXID.value  # "room.customer_mxid"
PROTECTED_KEY = "customer_mxid"


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
def _cache_fixture(room: Room, other_room: Room):
    Room.by_room_id.clear()
    room._add_to_cache()
    other_room._add_to_cache()
    yield
    Room.by_room_id.clear()


@pytest.mark.asyncio
async def test_cache_single_entry_per_room(room: Room, mocker: MockerFixture, config: Config):
    """A second Room with the same room_id overwrites the cache entry."""
    mocker.patch.object(Route, "update")
    other_route = Route(room=1, node_id="start", client="@bar:foo.com")
    second = Room(room_id=room.room_id)
    second.matrix_client = MagicMock()
    second.bot_mxid = "@bar:foo.com"
    second.route = other_route
    second.config = config

    second._add_to_cache()

    assert Room.by_room_id[room.room_id] is second
    assert len([k for k in Room.by_room_id if k == room.room_id]) == 1


@pytest.mark.asyncio
async def test_set_variable_does_not_affect_other_room(room: Room, other_room: Room):
    """Variables set on one room stay isolated from a different room_id."""
    await room.set_variable(variable_id="room.k", value="v")

    assert room._variables[Scopes.ROOM.value]["k"] == "v"
    assert other_room.variables == "{}"
    assert not hasattr(other_room, "_vars_cache") or other_room._variables == {}


@pytest.mark.asyncio
async def test_set_variable_custom_scope_isolated(room: Room, other_room: Room):
    """Custom scopes on one room stay isolated from a different room_id."""
    await room.set_variable(variable_id="k", value="v", scope="billing")

    assert room._variables["billing"]["k"] == "v"
    assert other_room.variables == "{}"
    assert not hasattr(other_room, "_vars_cache") or other_room._variables == {}


# ---------- ProtectedVars guard ------------------------------------------------


@pytest.mark.asyncio
async def test_set_variable_blocks_protected_var(room: Room, caplog):
    caplog.set_level(logging.WARNING)

    await room.set_variable(variable_id=PROTECTED_VAR, value="x")

    assert PROTECTED_KEY not in room._variables.get(Scopes.ROOM.value, {})
    assert any("Cannot set protected variable" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_set_variable_bypass_allows_protected_var(room: Room):
    await room.set_variable(variable_id=PROTECTED_VAR, value="x", bypass_protection=True)

    assert room._variables[Scopes.ROOM.value][PROTECTED_KEY] == "x"


@pytest.mark.asyncio
async def test_del_variable_blocks_protected_var(room: Room, caplog):
    caplog.set_level(logging.WARNING)
    await room.set_variable(variable_id=PROTECTED_VAR, value="x", bypass_protection=True)

    await room.del_variable(variable_id=PROTECTED_VAR)

    assert room._variables[Scopes.ROOM.value][PROTECTED_KEY] == "x"
    assert any("Cannot delete protected variable" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_del_variable_bypass_allows_protected_var(room: Room):
    await room.set_variable(variable_id=PROTECTED_VAR, value="x", bypass_protection=True)

    await room.del_variable(variable_id=PROTECTED_VAR, bypass_protection=True)

    assert PROTECTED_KEY not in room._variables.get(Scopes.ROOM.value, {})
