from __future__ import annotations

from json import JSONDecodeError
from unittest.mock import AsyncMock, MagicMock

import pytest

from menuflow.utils.types import Scopes


def make_mock_request(
    payload: dict | None,
    *,
    room_id: str = "!room:example.com",
    path: str | None = None,
    method: str = "POST",
) -> MagicMock:
    """Build a MagicMock that quacks like an aiohttp.web.Request.

    Parameters
    ----------
    payload:
        Body returned by ``await request.json()``. ``None`` makes ``json``
        raise ``JSONDecodeError`` to simulate invalid bodies.
    room_id:
        Value injected into ``match_info["room_id"]``.
    path / method:
        Set explicitly so handler log statements don't rely on MagicMock auto
        attributes.
    """
    req = MagicMock()
    req.method = method
    req.path = path or f"/v1/room/{room_id}/set_variables"
    req.match_info = {"room_id": room_id}
    if payload is None:
        req.json = AsyncMock(side_effect=JSONDecodeError("Expecting value", "x", 0))
    else:
        req.json = AsyncMock(return_value=payload)
    return req


@pytest.fixture
def patched_get_by_room_id(mocker):
    """Patches ``Room.get_by_room_id`` used by the client API handlers."""
    return mocker.patch(
        "menuflow.web.api.client.Room.get_by_room_id",
        new_callable=AsyncMock,
    )


@pytest.fixture
def mock_room(patched_get_by_room_id):
    """Returns a MagicMock room pre-wired to satisfy ``set_variables``.

    ``all_variables`` includes all private scopes plus a pre-existing custom
    scope ``catalog`` so tests can differentiate "new" vs "existing" custom
    scope branches in the handler.
    """
    room = MagicMock()
    room.set_external_variables = AsyncMock()
    room.set_variable = AsyncMock()
    room.all_variables = {
        Scopes.ROOM.value: {},
        Scopes.ROUTE.value: {},
        Scopes.NODE.value: {},
        Scopes.EXTERNAL.value: {},
        "catalog": {},
    }
    patched_get_by_room_id.return_value = room
    return room
