from __future__ import annotations

import json
import logging
from http import HTTPStatus
from json import JSONDecodeError
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from menuflow.utils.types import Scopes
from menuflow.web.api.client import set_variables

ROOM_ID = "!room:example.com"
BOT_MXID = "@bot:example.com"
HANDLER_LOGGER = "menuflow.api.client"


def make_mock_request(
    payload: dict | None,
    *,
    room_id: str = ROOM_ID,
    path: str | None = None,
    method: str = "POST",
) -> MagicMock:
    """Build a MagicMock that quacks like an aiohttp.web.Request."""
    req = MagicMock()
    req.method = method
    req.path = path or f"/v1/room/{room_id}/set_variables"
    req.match_info = {"room_id": room_id}
    if payload is None:
        req.json = AsyncMock(side_effect=JSONDecodeError("Expecting value", "x", 0))
    else:
        req.json = AsyncMock(return_value=payload)
    return req


# ---------- Body / dispatch ----------------------------------------------------


@pytest.mark.asyncio
async def test_body_not_json_returns_400(mock_room):
    resp = await set_variables(make_mock_request(None))

    assert resp.status == HTTPStatus.BAD_REQUEST
    body = json.loads(resp.text)
    assert body["detail"]["message"] == "Request body is not JSON"
    mock_room.set_external_variables.assert_not_awaited()
    mock_room.set_variable.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_by_room_id_called_with_room_id_and_bot_mxid(mock_room, patched_get_by_room_id):
    await set_variables(make_mock_request({"variables": {"a": 1}, "bot_mxid": BOT_MXID}))

    patched_get_by_room_id.assert_awaited_once_with(ROOM_ID, BOT_MXID)


@pytest.mark.asyncio
async def test_get_by_room_id_called_with_none_when_bot_mxid_missing(
    mock_room, patched_get_by_room_id
):
    await set_variables(make_mock_request({"variables": {"a": 1}}))
    patched_get_by_room_id.assert_awaited_once_with(ROOM_ID, None)


# ---------- External (custom_scope == False) ----------------------------------


@pytest.mark.asyncio
async def test_external_default_scope(mock_room):
    """custom_scope omitted -> variables go through set_external_variables."""
    resp = await set_variables(
        make_mock_request({"variables": {"token": "abc", "source": "api"}, "bot_mxid": BOT_MXID})
    )

    assert resp.status == HTTPStatus.OK
    mock_room.set_external_variables.assert_awaited_once_with(
        variables={"token": "abc", "source": "api"}
    )
    mock_room.set_variable.assert_not_awaited()


@pytest.mark.asyncio
async def test_external_missing_variables_calls_with_empty_dict(mock_room):
    """Body without ``variables`` still triggers set_external_variables({})."""
    resp = await set_variables(make_mock_request({"bot_mxid": BOT_MXID}))

    assert resp.status == HTTPStatus.OK
    mock_room.set_external_variables.assert_awaited_once_with(variables={})
    mock_room.set_variable.assert_not_awaited()


@pytest.mark.asyncio
async def test_external_with_conversation_uuid(mock_room):
    resp = await set_variables(
        make_mock_request(
            {"variables": {"k": "v"}, "bot_mxid": BOT_MXID, "conversation_uuid": "uuid-123"}
        )
    )

    assert resp.status == HTTPStatus.OK
    mock_room.set_external_variables.assert_awaited_once_with(variables={"k": "v"})
    mock_room.set_variable.assert_awaited_once_with(
        variable_id="room.conversation_uuid", value="uuid-123"
    )


# ---------- Custom scopes (custom_scope == True) ------------------------------


@pytest.mark.asyncio
async def test_custom_scope_private_scopes(mock_room):
    """custom_scope true: route/room/node values produce a set_variable each."""
    resp = await set_variables(
        make_mock_request(
            {
                "custom_scope": True,
                "bot_mxid": BOT_MXID,
                "variables": {
                    Scopes.ROUTE.value: {"trace_id": "t1"},
                    Scopes.ROOM.value: {"locale": "es"},
                    Scopes.NODE.value: {"step": 2},
                },
            }
        )
    )

    assert resp.status == HTTPStatus.OK
    mock_room.set_external_variables.assert_not_awaited()
    mock_room.set_variable.assert_has_awaits(
        [
            call(variable_id="trace_id", value="t1", scope=Scopes.ROUTE.value),
            call(variable_id="locale", value="es", scope=Scopes.ROOM.value),
            call(variable_id="step", value=2, scope=Scopes.NODE.value),
        ],
        any_order=True,
    )
    assert mock_room.set_variable.await_count == 3


@pytest.mark.asyncio
async def test_custom_scope_multiple_keys_same_scope(mock_room):
    resp = await set_variables(
        make_mock_request(
            {
                "custom_scope": True,
                "variables": {Scopes.ROUTE.value: {"a": 1, "b": 2}},
            }
        )
    )

    assert resp.status == HTTPStatus.OK
    mock_room.set_variable.assert_has_awaits(
        [
            call(variable_id="a", value=1, scope=Scopes.ROUTE.value),
            call(variable_id="b", value=2, scope=Scopes.ROUTE.value),
        ],
        any_order=True,
    )
    assert mock_room.set_variable.await_count == 2


@pytest.mark.asyncio
async def test_custom_scope_existing_custom_scope_no_new_scope_log(mock_room, caplog):
    """Custom scope already present in all_variables doesn't trigger 'new scope' log."""
    caplog.set_level(logging.INFO, logger=HANDLER_LOGGER)

    await set_variables(
        make_mock_request({"custom_scope": True, "variables": {"catalog": {"sku": "X1"}}})
    )

    mock_room.set_variable.assert_awaited_once_with(variable_id="sku", value="X1", scope="catalog")
    assert not any("Detecting new custom scope (catalog)" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_custom_scope_new_scope_emits_info_log(mock_room, caplog):
    """Custom scope missing from all_variables triggers the 'new scope' log."""
    caplog.set_level(logging.INFO, logger=HANDLER_LOGGER)

    await set_variables(
        make_mock_request({"custom_scope": True, "variables": {"billing": {"invoice_id": 99}}})
    )

    mock_room.set_variable.assert_awaited_once_with(
        variable_id="invoice_id", value=99, scope="billing"
    )
    assert any("Detecting new custom scope (billing)" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_custom_scope_ignores_conversation_uuid(mock_room):
    """conversation_uuid is only meaningful for the external branch."""
    await set_variables(
        make_mock_request(
            {
                "custom_scope": True,
                "conversation_uuid": "uuid-xxx",
                "variables": {Scopes.ROUTE.value: {"a": 1}},
            }
        )
    )

    mock_room.set_external_variables.assert_not_awaited()
    for awaited in mock_room.set_variable.await_args_list:
        assert awaited.kwargs.get("variable_id") != "room.conversation_uuid"


@pytest.mark.asyncio
async def test_custom_scope_empty_variables_is_noop(mock_room):
    resp = await set_variables(make_mock_request({"custom_scope": True, "variables": {}}))

    assert resp.status == HTTPStatus.OK
    mock_room.set_external_variables.assert_not_awaited()
    mock_room.set_variable.assert_not_awaited()


# ---------- Skip branches ------------------------------------------------------


@pytest.mark.parametrize("bad_value", [["x"], "string", 42, None, True])
@pytest.mark.asyncio
async def test_custom_scope_skips_non_dict_values(mock_room, caplog, bad_value):
    caplog.set_level(logging.WARNING, logger=HANDLER_LOGGER)

    resp = await set_variables(
        make_mock_request(
            {
                "custom_scope": True,
                "variables": {"weird": bad_value, Scopes.ROUTE.value: {"k": "v"}},
            }
        )
    )

    assert resp.status == HTTPStatus.OK
    mock_room.set_variable.assert_awaited_once_with(
        variable_id="k", value="v", scope=Scopes.ROUTE.value
    )
    assert any("Scope (weird) is not a dictionary" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_custom_scope_skips_empty_dict(mock_room, caplog):
    caplog.set_level(logging.WARNING, logger=HANDLER_LOGGER)

    resp = await set_variables(
        make_mock_request(
            {
                "custom_scope": True,
                "variables": {"empty": {}, Scopes.ROUTE.value: {"k": "v"}},
            }
        )
    )

    assert resp.status == HTTPStatus.OK
    mock_room.set_variable.assert_awaited_once_with(
        variable_id="k", value="v", scope=Scopes.ROUTE.value
    )
    assert any("Scope (empty) is empty" in r.message for r in caplog.records)


# ---------- Failure paths ------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_room_id_failure_returns_500(patched_get_by_room_id):
    patched_get_by_room_id.side_effect = RuntimeError("db down")

    resp = await set_variables(make_mock_request({"variables": {"a": "b"}, "bot_mxid": BOT_MXID}))

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    body = json.loads(resp.text)
    assert "db down" in body["detail"]["message"]


@pytest.mark.asyncio
async def test_set_variable_failure_returns_500(mock_room):
    mock_room.set_variable.side_effect = RuntimeError("boom")

    resp = await set_variables(
        make_mock_request({"custom_scope": True, "variables": {Scopes.ROUTE.value: {"k": "v"}}})
    )

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    body = json.loads(resp.text)
    assert "boom" in body["detail"]["message"]


@pytest.mark.asyncio
async def test_set_external_variables_failure_returns_500(mock_room):
    mock_room.set_external_variables.side_effect = RuntimeError("ext down")

    resp = await set_variables(make_mock_request({"variables": {"k": "v"}, "bot_mxid": BOT_MXID}))

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    body = json.loads(resp.text)
    assert "ext down" in body["detail"]["message"]


@pytest.mark.asyncio
async def test_get_by_room_id_returns_none_is_mapped_to_500(patched_get_by_room_id):
    """When the room can't be resolved the handler currently surfaces a 500."""
    patched_get_by_room_id.return_value = None

    resp = await set_variables(make_mock_request({"variables": {"k": "v"}, "bot_mxid": BOT_MXID}))

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
