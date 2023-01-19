from __future__ import annotations

import base64
from logging import getLogger
from typing import Dict, List

from aiohttp import BasicAuth
from mautrix.types import RoomID, UserID
from mautrix.util.logging import TraceLogger

from .config import Config
from .flow import Flow
from .middlewares.http import HTTPMiddleware
from .room import Room

log: TraceLogger = getLogger("menuflow.middleware")
flow_middlewares_cache: Dict[UserID, List[HTTPMiddleware]] = {}


def add_to_cache(*, user_id: UserID, middlewares: List[HTTPMiddleware]):
    flow_middlewares_cache[user_id] = middlewares


async def get_middlewares(user_id: UserID, customer_room_id: RoomID) -> Flow:
    if not flow_middlewares_cache.get(user_id):
        flow_file = Config(path=f"/data/flows/{user_id}.yaml", base_path="")
        flow_file.load()
        flow = Flow.deserialize(flow_file["menu"])
        room: Room = await Room.get_by_room_id(room_id=customer_room_id)
        middlewares: List[HTTPMiddleware] = flow._middlewares(room=room)
        add_to_cache(user_id=user_id, middlewares=middlewares)

    return flow_middlewares_cache[user_id]


async def start_auth_middleware(session, trace_config_ctx, params):
    trace_request_ctx = trace_config_ctx.__dict__
    if not trace_request_ctx["trace_request_ctx"]:
        return

    context_params: Dict = trace_request_ctx["trace_request_ctx"]
    room: Room = await Room.get_by_room_id(room_id=context_params.get("customer_room_id"))
    middlewares: List[HTTPMiddleware] = await get_middlewares(
        context_params.get("bot_mxid"), customer_room_id=context_params.get("customer_room_id")
    )

    for middleware in middlewares:
        if not str(params.url).startswith(middleware.url):
            continue

        params.headers.update(middleware._general_headers)

        if middleware.type == "jwt":
            if not await room.get_varibale("token"):
                await middleware.auth_request(session=session)

            params.headers.update(
                {"Authorization": f"{middleware._token_type} {await room.get_varibale('token')}"}
            )
            break
        elif middleware.type == "basic":
            auth_str = (
                f"{middleware._basic_auth['login']}:{middleware._basic_auth['password']}".encode(
                    "utf-8"
                )
            )
            params.headers.update(
                {"Authorization": f"Basic {base64.b64encode(auth_str).decode()}"}
            )


async def end_auth_middleware(session, trace_config_ctx, params):
    trace_request_ctx = trace_config_ctx.__dict__
    if not trace_request_ctx["trace_request_ctx"]:
        return

    if params.response.status == 401:
        log.debug("Token expired, refreshing token ...")
        context_params: Dict = trace_request_ctx["trace_request_ctx"]
        middlewares: List[HTTPMiddleware] = await get_middlewares(
            context_params.get("bot_mxid"), customer_room_id=context_params.get("customer_room_id")
        )

        for middleware in middlewares:
            if not str(params.url).startswith(middleware.url):
                continue

            if middleware.type == "jwt":
                await middleware.auth_request(session=session)
                break
