"""Tests for DELETE /v1/room/{room_id}."""

from __future__ import annotations

import json
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

import pytest

from menuflow.web.api.client import delete_room
from menuflow.webhook.webhook import Webhook

ROOM_ID = "!room:example.com"


def make_request(room_id: str = ROOM_ID) -> MagicMock:
    req = MagicMock()
    req.method = "DELETE"
    req.path = f"/v1/room/{room_id}"
    req.match_info = {"room_id": room_id}
    return req


@pytest.fixture
def isolated_webhook_cache():
    saved = dict(Webhook.by_room_id)
    Webhook.by_room_id.clear()
    yield
    Webhook.by_room_id.clear()
    Webhook.by_room_id.update(saved)


@pytest.mark.asyncio
async def test_delete_room_not_found(mocker):
    mocker.patch("menuflow.web.api.client.DBRoom.get_by_room_id", AsyncMock(return_value=None))

    resp = await delete_room(make_request())

    assert resp.status == HTTPStatus.NOT_FOUND
    body = json.loads(resp.text)
    assert body["detail"]["message"] == f"room_id '{ROOM_ID}' not found"


@pytest.mark.asyncio
async def test_delete_room_purges_and_clears_caches(mocker, isolated_webhook_cache):
    db_room = MagicMock()
    db_room.purge = AsyncMock()
    mocker.patch("menuflow.web.api.client.DBRoom.get_by_room_id", AsyncMock(return_value=db_room))
    remove_from_cache = mocker.patch("menuflow.web.api.client.Room.remove_from_cache")
    cancel_task = mocker.patch("menuflow.web.api.client.FlowUtil.cancel_task", AsyncMock())
    Webhook.by_room_id[ROOM_ID] = MagicMock()

    resp = await delete_room(make_request())

    assert resp.status == HTTPStatus.OK
    body = json.loads(resp.text)
    assert body["detail"]["message"] == f"Room '{ROOM_ID}' deleted successfully"
    db_room.purge.assert_awaited_once()
    remove_from_cache.assert_called_once_with(ROOM_ID)
    cancel_task.assert_awaited_once_with(task_name=ROOM_ID)
    assert ROOM_ID not in Webhook.by_room_id


@pytest.mark.asyncio
async def test_delete_room_server_error(mocker):
    db_room = MagicMock()
    db_room.purge = AsyncMock(side_effect=RuntimeError("db down"))
    mocker.patch("menuflow.web.api.client.DBRoom.get_by_room_id", AsyncMock(return_value=db_room))

    resp = await delete_room(make_request())

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    body = json.loads(resp.text)
    assert body["detail"]["message"] == "db down"
