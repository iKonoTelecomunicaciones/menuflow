from __future__ import annotations

import base64
from logging import getLogger
from typing import Dict

from mautrix.util.logging import TraceLogger

from .room import Room

log: TraceLogger = getLogger("menuflow.middleware")


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
    middleware = context_params.get("middleware")

    if not middleware:
        return

    if not str(params.url).startswith(middleware.url):
        return

    params.headers.update(middleware._general_headers)

    if middleware.type == "jwt":
        room: Room = await Room.get_by_room_id(room_id=context_params.get("customer_room_id"))
        if not await room.get_variable("token"):
            await middleware.auth_request(session=session)

        params.headers.update(
            {"Authorization": f"{middleware._token_type} {await room.get_variable('token')}"}
        )
    elif middleware.type == "basic":
        log.debug(f"middleware: {middleware.id} type: {middleware.type} executing ...")
        auth_str = (
            f"{middleware._basic_auth['login']}:{middleware._basic_auth['password']}".encode(
                "utf-8"
            )
        )
        params.headers.update({"Authorization": f"Basic {base64.b64encode(auth_str).decode()}"})


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

    context_params: Dict = trace_request_ctx["trace_request_ctx"]
    middleware = context_params.get("middleware")

    if not middleware:
        return

    if params.response.status == 401:
        log.debug("Token expired, refreshing token ...")
        if not str(params.url).startswith(middleware.url):
            return

        if middleware.type == "jwt":
            await middleware.auth_request(session=session)
