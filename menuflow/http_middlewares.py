from __future__ import annotations

import base64
from logging import getLogger
from types import SimpleNamespace
from typing import Dict

from aiohttp import ClientSession, TraceRequestEndParams, TraceRequestStartParams
from mautrix.util.logging import TraceLogger

from .room import Room

log: TraceLogger = getLogger("menuflow.middleware")


async def start_auth_middleware(
    session: ClientSession, trace_config_ctx: SimpleNamespace, params: TraceRequestStartParams
):
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
        log.info(f"There's no define middleware for this request: {params.url}")
        return

    if not str(params.url).startswith(middleware.url):
        log.info(f"The request url do not match with the meddleware url")
        return

    params.headers.update(middleware._general_headers)

    if middleware.type == "jwt":
        room: Room = await Room.get_by_room_id(room_id=context_params.get("customer_room_id"))
        room_variables: Dict = middleware.auth.variables.__dict__
        token_key: str = list(room_variables.keys())[0]

        if not await room.get_variable(token_key):
            await middleware.auth_request(session=session)

        params.headers.update(
            {"Authorization": f"{middleware._token_type} {await room.get_variable(token_key)}"}
        )
    elif middleware.type == "basic":
        log.info(f"middleware: {middleware.id} type: {middleware.type} executing ...")
        auth_str = (
            f"{middleware._basic_auth['login']}:{middleware._basic_auth['password']}".encode(
                "utf-8"
            )
        )
        params.headers.update({"Authorization": f"Basic {base64.b64encode(auth_str).decode()}"})


async def end_auth_middleware(
    session: ClientSession, trace_config_ctx: SimpleNamespace, params: TraceRequestEndParams
):
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
        log.info(f"There's no define middleware for this request: {params.url}")
        return

    if params.response.status == 401:
        if not str(params.url).startswith(middleware.url):
            log.info(f"The request url do not match with the meddleware url")
            return

        if middleware.type == "jwt":
            log.info("Token expired, refreshing token ...")
            await middleware.auth_request(session=session)
