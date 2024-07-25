from __future__ import annotations

import asyncio
from json import JSONDecodeError
from logging import Logger, getLogger
from typing import Dict, Optional

from aiohttp import web
from mautrix.client import Client as MatrixClient
from mautrix.errors import MatrixConnectionError, MatrixInvalidToken, MatrixRequestError
from mautrix.types import UserID

from ..config import Config
from ..db.client import Client as DBClient
from ..db.flow import Flow as DBFlow
from ..flow_utils import FlowUtils
from ..menu import MenuClient
from ..room import Room
from ..utils import Util
from .base import Base, routes
from .responses import resp

log: Logger = getLogger("menuflow.api.client")


async def _create_client(
    data: Dict, *, user_id: Optional[UserID] = None, flow_id: Optional[int] = None
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
    return resp.created(client.to_dict())


async def _reload_flow(client: MenuClient, flow_content: Optional[Dict] = None) -> web.Response:
    config: Config = Base.get_config()
    await client.flow_cls.load_flow(flow_mxid=client.id, content=flow_content, config=config)
    client.flow_cls.nodes_by_id = {}

    util = Util(config)
    await util.cancel_tasks()


@routes.post("/client/new")
async def create_client(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except JSONDecodeError:
        return resp.body_not_json

    new_flow_id = None
    if MenuClient.menuflow.config["menuflow.load_flow_from"] == "database":
        example_flow = {"menu": {"flow_variables": {}, "nodes": []}}
        new_flow = DBFlow(flow=example_flow)
        new_flow_id = await new_flow.insert()

    return await _create_client(data, flow_id=new_flow_id)


@routes.post("/room/{room_id}/set_variables")
async def set_variables(request: web.Request) -> web.Response:
    try:
        data: Dict = await request.json()
    except JSONDecodeError:
        return resp.body_not_json
    room_id = request.match_info["room_id"]
    variables = data.get("variables", {})
    bot_mxid = data.get("bot_mxid", None)
    room: Room = await Room.get_by_room_id(room_id, bot_mxid)

    await room.set_variable(variable_id="external", value=variables)

    return resp.ok({"detail": {"message": "Variables set successfully"}})


# Update or create new flow
@routes.put("/flow")
async def create_flow(request: web.Request) -> web.Response:
    config: Config = Base.get_config()
    try:
        data: Dict = await request.json()
    except JSONDecodeError:
        return resp.body_not_json

    flow_id = data.get("id", None)
    incoming_flow = data.get("flow", None)

    if not incoming_flow:
        return resp.bad_request("Incoming flow is required")

    if flow_id:
        flow = await DBFlow.get_by_id(flow_id)
        flow.flow = incoming_flow
        await flow.update()

        if config["menuflow.load_flow_from"] == "database":
            db_clients = await DBClient.get_by_flow_id(flow_id)
            for db_client in db_clients:
                client = MenuClient.cache[db_client.id]
                await _reload_flow(client, incoming_flow)
        message = "Flow updated successfully"
    else:
        new_flow = DBFlow(flow=incoming_flow)
        await new_flow.insert()
        message = "Flow created successfully"

    return resp.ok({"detail": {"message": message}})


@routes.get("/flow")
async def get_flow(request: web.Request) -> web.Response:
    flow_id = request.query.get("id", None)
    client_mxid = request.query.get("client_mxid", None)
    if flow_id:
        flow = await DBFlow.get_by_id(int(flow_id))
        if not flow:
            return resp.not_found(f"Flow with ID {flow_id} not found")
        data = flow.serialize()
    elif client_mxid:
        flow = await DBFlow.get_by_mxid(client_mxid)
        if not flow:
            return resp.not_found(f"Flow with mxid {client_mxid} not found")
        data = flow.serialize()
    else:
        flows = await DBFlow.all()
        data = {"flows": flows}

    return resp.ok(data)


@routes.patch("/client/{mxid}/flow")
async def update_client(request: web.Request) -> web.Response:
    mxid = request.match_info["mxid"]
    client: Optional[MenuClient] = MenuClient.cache.get(mxid)
    if not client:
        return resp.client_not_found(mxid)

    try:
        data: Dict = await request.json()
    except JSONDecodeError:
        return resp.body_not_json

    flow_id = data.get("flow_id", None)
    if not flow_id:
        return resp.bad_request("Flow ID is required")

    flow_db = await DBFlow.get_by_id(flow_id)
    if not flow_db:
        return resp.bad_request("Flow not found")

    client.flow = flow_id
    await _reload_flow(client, flow_db.flow)

    await client.update()
    return resp.ok(client.to_dict())


@routes.post("/client/{mxid}/flow/reload")
async def reload_client_flow(request: web.Request) -> web.Response:
    mxid = request.match_info["mxid"]
    client: Optional[MenuClient] = MenuClient.cache.get(mxid)
    if not client:
        return resp.client_not_found(mxid)

    await _reload_flow(client)

    return resp.ok(client.to_dict())


@routes.patch("/client/{mxid}/{action}")
async def enable_disable_client(request: web.Request) -> web.Response:
    mxid = request.match_info["mxid"]
    action = request.match_info["action"]
    client: Optional[MenuClient] = await MenuClient.get(mxid)
    if not client:
        return resp.client_not_found(mxid)

    if action == "enable":
        client.enabled = True
        await client.start()
    elif action == "disable":
        client.enabled = False
        asyncio.create_task(client.leave_rooms(), name=f"{mxid}-leave_rooms")
        await client.stop()
    else:
        return resp.bad_request("Invalid action provided")

    await client.update()
    return resp.ok({"detail": {"message": f"Client {action}d successfully"}})


@routes.get("/client/email_servers")
async def get_id_email_servers(request: web.Request) -> web.Response:
    name_email_servers = [name for name in FlowUtils.email_servers_by_id.keys()]

    return resp.ok({"email_servers": name_email_servers})
