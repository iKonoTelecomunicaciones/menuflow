from __future__ import annotations

from json import JSONDecodeError
from typing import Dict

from aiohttp import web
from mautrix.client import Client as MatrixClient
from mautrix.errors import MatrixConnectionError, MatrixInvalidToken, MatrixRequestError
from mautrix.types import UserID

from ..menu import MenuClient
from ..room import Room
from .base import routes
from .responses import resp


async def _create_client(user_id: UserID | None, data: dict) -> web.Response:
    homeserver = data.get("homeserver", None)
    access_token = data.get("access_token", None)
    device_id = data.get("device_id", None)
    new_client = MatrixClient(
        mxid="@not:a.mxid",
        base_url=homeserver,
        token=access_token,
        client_session=MenuClient.http_client,
    )
    try:
        whoami = await new_client.whoami()
    except MatrixInvalidToken:
        return resp.bad_client_access_token
    except MatrixRequestError:
        return resp.bad_client_access_details
    except MatrixConnectionError:
        return resp.bad_client_connection_details
    if user_id is None:
        existing_client = await MenuClient.get(whoami.user_id)
        if existing_client is not None:
            return resp.user_exists
    elif whoami.user_id != user_id:
        return resp.mxid_mismatch(whoami.user_id)
    elif whoami.device_id and device_id and whoami.device_id != device_id:
        return resp.device_id_mismatch(whoami.device_id)
    client: MenuClient = await MenuClient.get(
        whoami.user_id, homeserver=homeserver, access_token=access_token, device_id=device_id
    )
    client.enabled = data.get("enabled", True)
    client.autojoin = data.get("autojoin", True)
    await client.update()
    await client.start()
    return resp.created(client.to_dict())


@routes.post("/client/new")
async def create_client(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except JSONDecodeError:
        return resp.body_not_json
    return await _create_client(None, data)


@routes.post("/room/{room_id}/set_variables")
async def set_variables(request: web.Request) -> web.Response:
    try:
        data: Dict = await request.json()
    except JSONDecodeError:
        return resp.body_not_json
    room_id = request.match_info["room_id"]
    room = await Room.get_by_room_id(room_id)
    variables = data.get("variables", {})

    await room.set_variables(variables=variables)

    return resp.ok
