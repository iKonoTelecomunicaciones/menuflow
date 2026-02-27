from __future__ import annotations

import asyncio
import json
from json import JSONDecodeError
from logging import Logger, getLogger
from typing import Dict, Optional

from aiohttp import web
from mautrix.client import Client as MatrixClient
from mautrix.errors import MatrixConnectionError, MatrixInvalidToken, MatrixRequestError
from mautrix.types import UserID

from ...config import Config
from ...db.flow import Flow as DBFlow
from ...db.module import Module as DBModule
from ...db.room import Room as DBRoom
from ...db.route import Route as DBRoute
from ...db.tag import Tag as DBTag
from ...menu import MenuClient
from ...room import Room
from ..base import get_config, routes
from ..docs.client import (
    create_client_doc,
    enable_disable_client_doc,
    get_variables_doc,
    reload_client_flow_doc,
    set_variables_doc,
    status_doc,
    update_client_doc,
)
from ..responses import resp
from ..util import Util

log: Logger = getLogger("menuflow.api.client")


async def _create_client(
    data: Dict,
    *,
    user_id: Optional[UserID] = None,
    flow_id: Optional[int] = None,
    uuid: Optional[str] = None,
) -> MenuClient | web.Response:
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
        whoami.user_id,
        homeserver=homeserver,
        access_token=access_token,
        device_id=device_id,
        flow_id=flow_id,
    )
    client.enabled = data.get("enabled", True)
    client.autojoin = data.get("autojoin", True)
    await client.update()
    await client.start()
    return resp.created(client.to_dict(), uuid=uuid)


@routes.post("/v1/client/new")
@Util.docstring(create_client_doc)
async def create_client(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Creating client")

    try:
        data = await request.json()
    except JSONDecodeError:
        return resp.body_not_json

    new_flow_id = None
    if MenuClient.menuflow.config["menuflow.load_flow_from"] == "database":
        new_flow = DBFlow(flow_vars={})
        new_flow_id = await new_flow.insert()

        current_tag = DBTag(
            flow_id=new_flow_id, name="current", flow_vars={}, author="system", active=True
        )
        tag_id = await current_tag.insert()

        main_module = DBModule(
            flow_id=new_flow_id,
            name="Main",
            nodes=[
                {
                    "x": 0,
                    "y": 0,
                    "id": "start",
                    "name": "start",
                    "text": "",
                    "type": "message",
                    "module": "Main",
                    "message_type": "m.text",
                    "o_connection": "",
                }
            ],
            position={},
            tag_id=tag_id,
        )
        await main_module.insert()
        log.info(f"({uuid}) -> Created new flow with ID {new_flow_id} for client")

    return await _create_client(data, flow_id=new_flow_id, uuid=uuid)


@routes.post("/v1/room/{room_id}/set_variables")
@Util.docstring(set_variables_doc)
async def set_variables(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Setting variables")

    try:
        data: Dict = await request.json()
    except JSONDecodeError:
        return resp.body_not_json(uuid)

    room_id = request.match_info["room_id"]
    variables = data.get("variables", {})
    bot_mxid = data.get("bot_mxid", None)
    conversation_uuid = data.get("conversation_uuid", None)

    try:
        room: Room = await Room.get_by_room_id(room_id, bot_mxid)
        await room.set_variable(variable_id="external", value=variables)
        if conversation_uuid:
            await room.set_variable(variable_id="room.conversation_uuid", value=conversation_uuid)
    except Exception as e:
        return resp.server_error(str(e), uuid)

    return resp.success(message="Variables set successfully", uuid=uuid)


@routes.patch("/v1/client/{mxid}/flow")
@Util.docstring(update_client_doc)
async def update_client(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Updating client")

    mxid = request.match_info["mxid"]
    client: Optional[MenuClient] = await MenuClient.get(mxid)
    if not client:
        return resp.client_not_found(mxid, uuid)

    try:
        data: Dict = await request.json()
    except JSONDecodeError:
        return resp.body_not_json(uuid)

    flow_id = data.get("flow_id", None)
    if not flow_id:
        return resp.bad_request("Flow ID is required", uuid)

    flow_db = await DBFlow.get_by_id(flow_id)
    if not flow_db:
        return resp.not_found("Flow not found", uuid)

    client.flow = flow_id
    modules = await DBModule.all(flow_db.id)
    nodes = [node for module in modules for node in module.get("nodes", [])]
    config: Config = get_config()
    await client.flow_cls.load_flow(
        flow_mxid=client.id,
        content={"flow_variables": flow_db.flow_vars, "nodes": nodes},
        config=config,
    )

    await client.update()
    return resp.success(data=client.to_dict(), uuid=uuid)


@routes.post("/v1/client/{mxid}/flow/reload")
@Util.docstring(reload_client_flow_doc)
async def reload_client_flow(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Reloading client flow")

    mxid = request.match_info["mxid"]
    client: Optional[MenuClient] = MenuClient.cache.get(mxid)
    if not client:
        return resp.client_not_found(mxid, uuid)

    config: Config = get_config()
    await client.flow_cls.load_flow(flow_mxid=client.id, config=config)

    return resp.success(message="Flow reloaded successfully", uuid=uuid)


@routes.patch("/v1/client/{mxid}/{action}")
@Util.docstring(enable_disable_client_doc)
async def enable_disable_client(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Enabling/disabling client")

    mxid = request.match_info["mxid"]
    action = request.match_info["action"]
    client: Optional[MenuClient] = await MenuClient.get(mxid)
    if not client:
        return resp.client_not_found(mxid, uuid)

    if action == "enable":
        client.enabled = True
        await client.start()
    elif action == "disable":
        client.enabled = False
        asyncio.create_task(client.leave_rooms(), name=f"{mxid}-leave_rooms")
        await client.stop()
    else:
        return resp.bad_request("Invalid action provided", uuid)

    await client.update()
    return resp.success(message=f"Client {action}d successfully", uuid=uuid)


@routes.get("/v1/room/{room_id}/get_variables", allow_head=False)
@Util.docstring(get_variables_doc)
async def get_variables(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Getting variables")

    room_id = request.match_info["room_id"]
    bot_mxid = request.query.get("bot_mxid", None)
    scopes = request.query.getall("scopes", ["room", "route", "node"])
    response = {}

    try:
        room = await DBRoom.get_by_room_id(room_id)
        if not room:
            return resp.not_found(f"room_id '{room_id}' not found", uuid)

        if not bot_mxid:
            bot_mxid = room._variables.get("current_bot_mxid")
            if not bot_mxid:
                return resp.not_found("current_bot_mxid not found in the room variables", uuid)

        route = await DBRoute.get_by_room_and_client(room=room.id, client=bot_mxid, create=False)
        if not route:
            return resp.not_found(f"Client '{bot_mxid}' not found in room", uuid)

        for scope in scopes:
            match scope:
                case "room":
                    response[scope] = room._variables
                case "route":
                    response[scope] = route._variables
                case "node":
                    response[scope] = route._node_vars
                case _:
                    log.warning(f"({uuid}) -> Invalid scope: {scope}, skipping")

    except Exception as e:
        return resp.server_error(str(e), uuid)

    return (
        resp.success(data=response, uuid=uuid)
        if response
        else resp.not_found("Scopes not found", uuid)
    )


@routes.get("/v1/room/{room_id}/status", allow_head=False)
@Util.docstring(status_doc)
async def status(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Getting variables")

    room_id = request.match_info["room_id"]
    bot_mxid = request.query.get("bot_mxid", None)

    try:
        room = await DBRoom.get_by_room_id(room_id)
        if not room:
            return resp.not_found(f"room_id '{room_id}' not found", uuid)

        if not bot_mxid:
            bot_mxid = room._variables.get("current_bot_mxid")
            if not bot_mxid:
                return resp.not_found(
                    "current_bot_mxid not found in the room variables, send the bot_mxid in the query parameters",
                    uuid,
                )

        route = await DBRoute.get_by_room_and_client(room=room.id, client=bot_mxid, create=False)
        if not route:
            return resp.not_found(f"Client '{bot_mxid}' not found in room", uuid)

        response = {"status": route.state.value, "node_id": route.node_id, "client": route.client}

    except Exception as e:
        return resp.server_error(str(e), uuid)

    return resp.success(data=response, uuid=uuid)
