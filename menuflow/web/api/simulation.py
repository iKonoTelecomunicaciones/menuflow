from __future__ import annotations

import asyncio
import logging
from json import JSONDecodeError
from time import time
from typing import Any
from uuid import uuid4

from aiohttp import web
from mautrix.types import MessageEvent, StateEvent

from ...menu import MenuClient
from ..base import routes
from ..docs.simulation import simulate_event_doc
from ..responses import resp
from ..util import Util

log = logging.getLogger("menuflow.api.simulation")

VALID_EVENT_TYPES = frozenset({"join", "leave", "message"})


def _build_member_event(
    *,
    room_id: str,
    bot_mxid: str,
    sender: str,
    event_id: str,
    origin_server_ts: int,
    membership: str,
    prev_membership: str | None,
) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "type": "m.room.member",
        "room_id": room_id,
        "sender": sender,
        "state_key": bot_mxid,
        "event_id": event_id,
        "origin_server_ts": origin_server_ts,
        "content": {"membership": membership},
    }
    if prev_membership is not None:
        raw["unsigned"] = {"prev_content": {"membership": prev_membership}}
    return raw


def _build_message_event(
    *,
    room_id: str,
    sender: str,
    event_id: str,
    origin_server_ts: int,
    body: str,
    msgtype: str,
) -> dict[str, Any]:
    return {
        "type": "m.room.message",
        "room_id": room_id,
        "sender": sender,
        "event_id": event_id,
        "origin_server_ts": origin_server_ts,
        "content": {"msgtype": msgtype, "body": body},
    }


@routes.post("/v1/client/{mxid}/simulate/event")
# @Util.docstring(simulate_event_doc)
async def simulate_event(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    mxid = request.match_info["mxid"]
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Simulate Matrix event")

    try:
        data = await request.json()
    except JSONDecodeError:
        return resp.body_not_json

    event_type = data.get("event_type")
    room_id = data.get("room_id")

    if not event_type or event_type not in VALID_EVENT_TYPES:
        return resp.bad_request(
            "event_type is required and must be one of: join, leave, message", uuid=uuid
        )
    if not room_id:
        return resp.bad_request("room_id is required", uuid=uuid)

    event_id_raw = data.get("event_id")
    event_id = (
        event_id_raw if isinstance(event_id_raw, str) and event_id_raw else f"$sim-{uuid4().hex}"
    )

    ts_raw = data.get("timestamp")
    if ts_raw is None:
        ts = int(time() * 1000)
    else:
        try:
            ts = int(ts_raw)
        except (TypeError, ValueError):
            return resp.bad_request(
                "timestamp must be an integer (milliseconds since epoch)", uuid=uuid
            )

    client = MenuClient.cache.get(mxid)
    if not client:
        return resp.client_not_found(mxid, uuid=uuid)

    handler = client.matrix_handler

    if event_type == "message":
        sender = data.get("sender")
        body = data.get("body")
        if not sender or not isinstance(sender, str):
            return resp.bad_request("sender is required for message events", uuid=uuid)
        if body is None or not isinstance(body, str):
            return resp.bad_request("body is required for message events", uuid=uuid)
        if sender == mxid:
            return resp.bad_request(
                "sender must not be the bot mxid (the bot ignores its own messages)", uuid=uuid
            )
        msgtype = data.get("msgtype") or "m.text"
        if not isinstance(msgtype, str):
            return resp.bad_request("msgtype must be a string", uuid=uuid)

        raw = _build_message_event(
            room_id=room_id,
            sender=sender,
            event_id=event_id,
            origin_server_ts=ts,
            body=body,
            msgtype=msgtype,
        )
        try:
            evt = MessageEvent.deserialize(raw)
        except Exception as e:
            log.exception("(%s) Failed to deserialize simulated message", uuid)
            return resp.unprocessable_entity(f"Invalid message event payload: {e}", uuid=uuid)

        async def _run() -> None:
            try:
                await handler.handle_message(evt)
            except Exception:
                log.exception("(%s) Simulated message handler failed", uuid)

        asyncio.create_task(_run())

    elif event_type == "join":
        sender = data.get("sender") if isinstance(data.get("sender"), str) else mxid
        raw = _build_member_event(
            room_id=room_id,
            bot_mxid=mxid,
            sender=sender,
            event_id=event_id,
            origin_server_ts=ts,
            membership="join",
            prev_membership="invite",
        )
        try:
            evt = StateEvent.deserialize(raw)
        except Exception as e:
            log.exception("(%s) Failed to deserialize simulated join", uuid)
            return resp.unprocessable_entity(f"Invalid join event payload: {e}", uuid=uuid)

        async def _run() -> None:
            try:
                await handler.handle_join(evt)
            except Exception:
                log.exception("(%s) Simulated join handler failed", uuid)

        asyncio.create_task(_run())

    else:  # leave
        sender = data.get("sender") if isinstance(data.get("sender"), str) else mxid
        raw = _build_member_event(
            room_id=room_id,
            bot_mxid=mxid,
            sender=sender,
            event_id=event_id,
            origin_server_ts=ts,
            membership="leave",
            prev_membership=None,
        )
        try:
            evt = StateEvent.deserialize(raw)
        except Exception as e:
            log.exception("(%s) Failed to deserialize simulated leave", uuid)
            return resp.unprocessable_entity(f"Invalid leave event payload: {e}", uuid=uuid)

        async def _run() -> None:
            try:
                await handler.handle_leave(evt)
            except Exception:
                log.exception("(%s) Simulated leave handler failed", uuid)

        asyncio.create_task(_run())

    _resp = {"event_id": event_id, "room_id": room_id, "event_type": event_type, "timestamp": ts}

    return resp.success(message=f"Simulated {event_type} event dispatched", uuid=uuid, data=_resp)
