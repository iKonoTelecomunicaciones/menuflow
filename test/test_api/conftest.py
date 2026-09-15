from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from menuflow.utils.types import Scopes


@pytest.fixture
def patched_get_by_room_id(mocker):
    """Patches ``Room.get_by_room_id`` used by the client API handlers."""
    return mocker.patch(
        "menuflow.web.api.client.Room.get_by_room_id",
        new_callable=AsyncMock,
    )


@pytest.fixture
def patched_db_room_get_by_room_id(mocker):
    """Patches ``DBRoom.get_by_room_id`` used to resolve ``current_bot_mxid``."""
    return mocker.patch(
        "menuflow.web.api.client.DBRoom.get_by_room_id",
        new_callable=AsyncMock,
    )


@pytest.fixture
def mock_db_room(patched_db_room_get_by_room_id):
    """DB room with ``room.current_bot_mxid`` set for conversation resolution."""
    db_room = MagicMock()
    db_room._variables = {"room": {"current_bot_mxid": "@bot:example.com"}}
    patched_db_room_get_by_room_id.return_value = db_room
    return db_room


@pytest.fixture
def mock_room(patched_get_by_room_id):
    """Returns a MagicMock room pre-wired to satisfy ``set_variables``.

    ``all_variables`` includes all private scopes plus a pre-existing custom
    scope ``catalog`` so tests can differentiate "new" vs "existing" custom
    scope branches in the handler.
    """
    room = MagicMock()
    room.set_conversation_variables = AsyncMock()
    room.set_variable = AsyncMock()
    room.all_variables = {
        Scopes.ROOM.value: {},
        Scopes.ROUTE.value: {},
        Scopes.NODE.value: {},
        "catalog": {},
    }
    patched_get_by_room_id.return_value = room
    return room
