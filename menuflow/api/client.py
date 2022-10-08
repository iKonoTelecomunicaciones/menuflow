from __future__ import annotations

from json import JSONDecodeError

from aiohttp import web

from mautrix.client import Client as MatrixClient
from mautrix.errors import MatrixConnectionError, MatrixInvalidToken, MatrixRequestError
from mautrix.types import UserID

from ..menu import MenuClient
from .base import get_config, routes
from .responses import resp


@routes.get("/clients")
async def get_clients(_: web.Request) -> web.Response:
    return resp.found([client.to_dict() for client in MenuClient.cache.values()])


@routes.get("/client/{id}")
async def get_client(request: web.Request) -> web.Response:
    user_id = request.match_info.get("id", None)
    client = await MenuClient.get(user_id)
    if not client:
        return resp.client_not_found
    return resp.found(client.to_dict())


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
    await client.start(config=get_config())
    return resp.created(client.to_dict())


async def _update_client(client: MenuClient, data: dict, is_login: bool = False) -> web.Response:
    try:
        await client.update_access_details(
            data.get("access_token"), data.get("homeserver"), data.get("device_id")
        )
    except MatrixInvalidToken:
        return resp.bad_client_access_token
    except MatrixRequestError:
        return resp.bad_client_access_details
    except MatrixConnectionError:
        return resp.bad_client_connection_details
    except ValueError as e:
        str_err = str(e)
        if str_err.startswith("MXID mismatch"):
            return resp.mxid_mismatch(str(e)[len("MXID mismatch: ") :])
        elif str_err.startswith("Device ID mismatch"):
            return resp.device_id_mismatch(str(e)[len("Device ID mismatch: ") :])
    await client.update_avatar_url(data.get("avatar_url"), save=False)
    await client.update_displayname(data.get("displayname"), save=False)
    await client.update_started(data.get("started"))
    await client.update_enabled(data.get("enabled"), save=False)
    await client.update_autojoin(data.get("autojoin"), save=False)
    await client.update_online(data.get("online"), save=False)
    await client.update_sync(data.get("sync"), save=False)
    await client.update()
    return resp.updated(client.to_dict(), is_login=is_login)


async def _create_or_update_client(
    user_id: UserID, data: dict, is_login: bool = False
) -> web.Response:
    client = await MenuClient.get(user_id)
    if not client:
        return await _create_client(user_id, data)
    else:
        return await _update_client(client, data, is_login=is_login)


@routes.post("/client/new")
async def create_client(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except JSONDecodeError:
        return resp.body_not_json
    return await _create_client(None, data)


@routes.put("/client/{id}")
async def update_client(request: web.Request) -> web.Response:
    user_id = request.match_info["id"]
    try:
        data = await request.json()
    except JSONDecodeError:
        return resp.body_not_json
    return await _create_or_update_client(user_id, data)


@routes.delete("/client/{id}")
async def delete_client(request: web.Request) -> web.Response:
    user_id = request.match_info["id"]
    client = await MenuClient.get(user_id)
    if not client:
        return resp.client_not_found
    if len(client.references) > 0:
        return resp.client_in_use
    if client.started:
        await client.stop()
    await client.delete()
    return resp.deleted


@routes.post("/client/{id}/clearcache")
async def clear_client_cache(request: web.Request) -> web.Response:
    user_id = request.match_info["id"]
    client = await MenuClient.get(user_id)
    if not client:
        return resp.client_not_found
    await client.clear_cache()
    return resp.ok
