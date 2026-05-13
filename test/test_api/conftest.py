from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from menuflow.utils.types import Scopes


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
