from __future__ import annotations

import base64
from logging import getLogger
from typing import Dict, List

from mautrix.types import RoomID, UserID
from mautrix.util.logging import TraceLogger

from .config import Config
from .flow import Flow
from .middlewares.http import HTTPMiddleware
from .room import Room

log: TraceLogger = getLogger("menuflow.middleware")
flow_middlewares_cache: Dict[UserID, List[HTTPMiddleware]] = {}


def add_to_cache(*, user_id: UserID, middlewares: List[HTTPMiddleware]):
    """It adds a list of HTTP middlewares to a cache

    Parameters
    ----------
    user_id : UserID
        The user ID of the bot.
    middlewares : List[HTTPMiddleware]
        A list of middlewares to be added to the cache.

    """
    flow_middlewares_cache[user_id] = middlewares


async def get_middlewares(user_id: UserID, customer_room_id: RoomID) -> List[HTTPMiddleware]:
    """It loads the flow file for the user, deserializes it,
    gets the middlewares for the flow, and adds it to the cache

    Parameters
    ----------
    user_id : UserID
        The user id of the bot
    customer_room_id : RoomID
        The room ID of the customer.

    Returns
    -------
        A list of middlewares

    """

    if not flow_middlewares_cache.get(user_id):
        flow_file = Config(path=f"/data/flows/{user_id}.yaml", base_path="")
        flow_file.load()
        flow = Flow.deserialize(flow_file["menu"])
        room: Room = await Room.get_by_room_id(room_id=customer_room_id)
        middlewares: List[HTTPMiddleware] = flow._middlewares(room=room)
        add_to_cache(user_id=user_id, middlewares=middlewares)

    return flow_middlewares_cache[user_id]


async def start_auth_middleware(session, trace_config_ctx, params):
    """It checks if the request is going to a URL that has a middleware,
    and if so, it adds the appropriate headers to the request

    Parameters
    ----------
    session
        The session object that is used to make the request.
    trace_config_ctx
        This is the context of the request.
    params
        Dict - the parameters of the request

    """
    trace_request_ctx: Dict = trace_config_ctx.__dict__
    if not trace_request_ctx.get("trace_request_ctx"):
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
            if not await room.get_variable("token"):
                await middleware.auth_request(session=session)

            params.headers.update(
                {"Authorization": f"{middleware._token_type} {await room.get_variable('token')}"}
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
    """If the response status is 401, refresh the token and retry the request

    Parameters
    ----------
    session
        The session object that is used to make the request.
    trace_config_ctx
        This is the context of the request. It contains the request parameters.
    params
        The parameters of the request.

    Returns
    -------
        The response from the request.

    """

    trace_request_ctx: Dict = trace_config_ctx.__dict__
    if not trace_request_ctx.get("trace_request_ctx"):
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
