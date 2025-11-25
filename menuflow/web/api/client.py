from __future__ import annotations

import asyncio
from json import JSONDecodeError
from logging import Logger, getLogger
from typing import Dict, Optional

from aiohttp import web
from mautrix.client import Client as MatrixClient
from mautrix.errors import MatrixConnectionError, MatrixInvalidToken, MatrixRequestError
from mautrix.types import UserID

from ...config import Config
from ...db.flow import Flow as DBFlow
from ...db.room import Room as DBRoom
from ...db.route import Route as DBRoute
from ...menu import MenuClient
from ...room import Room
from ..base import get_config, routes
from ..responses import resp

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


@routes.post("/v1/client/new")
async def create_client(request: web.Request) -> web.Response:
    """
    ---
    summary: Create a new client
    description: Create a new client with the provided homeserver and access token
    tags:
        - Client

    requestBody:
        required: false
        content:
            application/json:
                schema:
                    type: object
                    properties:
                        homeserver:
                            type: string
                        access_token:
                            type: string
                        device_id:
                            type: string
                        enabled:
                            type: boolean
                        autojoin:
                            type: boolean
                    required:
                        - homeserver
                        - access_token
                example:
                    homeserver: "https://matrix.org"
                    access_token: "sk_MDAxOGxvY2F0aW9uIG1hdXRyaXgub3JnCjAwMTBja"
                    device_id: "DFKEN36"
                    enabled: true
                    autojoin: true
    responses:
        '201':
            $ref: '#/components/responses/CreateClientSuccess'
        '400':
            $ref: '#/components/responses/CreateClientBadRequest'
    """
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


@routes.post("/v1/room/{room_id}/set_variables")
async def set_variables(request: web.Request) -> web.Response:
    """
    ---
    summary: Create a new client
    description: Create a new client with the provided homeserver and access token
    tags:
        - Client

    parameters:
        - name: room_id
          in: path
          required: true
          description: The room ID to set variables for
          schema:
            type: string
          example: "!vOmHZZMQibXsynuNFm:example.com"

    requestBody:
        required: true
        content:
            application/json:
                schema:
                    type: object
                    properties:
                        variables:
                            type: object
                        bot_mxid:
                            type: string
                example:
                    variables:
                        var1: value
                        var2: value
                    bot_mxid: "@bot:example.com"
    responses:
        '201':
            $ref: '#/components/responses/VariablesSetSuccess'
    """
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


@routes.patch("/v1/client/{mxid}/flow")
async def update_client(request: web.Request) -> web.Response:
    """
    ---
    summary: Update a client's flow
    description: Update the flow of a client

    tags:
        - Client

    parameters:
        - name: mxid
          in: path
          required: true
          description: The Matrix user ID of the client
          schema:
            type: string
          example: "@client:example.com"

    requestBody:
        required: true
        content:
            application/json:
                schema:
                    type: object
                    properties:
                        flow_id:
                            type: integer
                    required:
                        - flow_id
                example:
                    flow_id: 1

    responses:
        '200':
            $ref: '#/components/responses/ClientFlowUpdated'
        '400':
            $ref: '#/components/responses/ClientUpdateFlowBadRequest'
        '404':
            $ref: '#/components/responses/ClientUpdateFlowNotFound'
    """
    mxid = request.match_info["mxid"]
    client: Optional[MenuClient] = await MenuClient.get(mxid)
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
        return resp.not_found("Flow not found")

    client.flow = flow_id
    config: Config = get_config()
    await client.flow_cls.load_flow(flow_mxid=client.id, content=flow_db.flow, config=config)

    await client.update()
    return resp.ok(client.to_dict())


@routes.post("/v1/client/{mxid}/flow/reload")
async def reload_client_flow(request: web.Request) -> web.Response:
    """
    ---
    summary: Reload a client's flow
    description: Reload the flow of a client

    tags:
        - Client

    parameters:
        - name: mxid
          in: path
          required: true
          description: The Matrix user ID of the client
          schema:
            type: string
          example: "@client:example.com"

    responses:
        '200':
            $ref: '#/components/responses/ClientFlowReloaded'
        '404':
            $ref: '#/components/responses/ClientReloadFlowNotFound'
    """
    mxid = request.match_info["mxid"]
    client: Optional[MenuClient] = MenuClient.cache.get(mxid)
    if not client:
        return resp.client_not_found(mxid)

    config: Config = get_config()
    await client.flow_cls.load_flow(flow_mxid=client.id, config=config)

    return resp.ok({"detail": {"message": "Flow reloaded successfully"}})


@routes.patch("/v1/client/{mxid}/{action}")
async def enable_disable_client(request: web.Request) -> web.Response:
    """
    ---
    summary: Enable or disable a client
    description: Enable or disable a client

    tags:
        - Client

    parameters:
        - name: mxid
          in: path
          required: true
          description: The Matrix user ID of the client
          schema:
            type: string
          example: "@client:example.com"
        - name: action
          in: path
          required: true
          description: The action to perform
          schema:
            type: string
          example: "enable | disable"

    responses:
        '200':
            $ref: '#/components/responses/ClientEnabledOrDisabled'
        '400':
            $ref: '#/components/responses/ClientEnableOrDisableBadRequest'
        '404':
            $ref: '#/components/responses/ClientEnableOrDisableNotFound'
    """
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


@routes.get("/v1/room/{room_id}/get_variables", allow_head=False)
async def get_variables(request: web.Request) -> web.Response:
    """
    ---
    summary: Get variables
    description: Get variables
    tags:
        - Room

    parameters:
        - name: room_id
          in: path
          required: true
          description: The room ID to set variables for
          schema:
            type: string
          example: "!vOmHZZMQibXsynuNFm:example.com"

        - name: bot_mxid
          in: query
          description: The Matrix user ID of the client
          schema:
            type: string
          example: "@bot:example.com"

        - name: scopes
          in: query
          required: false
          description: The scopes of the variables to get. If not provided, all variables will be returned.
          schema:
            type: array
            default: ["room", "route"]
            items:
              type: string

    responses:
        '200':
            $ref: '#/components/responses/GetVariablesSuccess'
        '404':
            $ref: '#/components/responses/GetVariablesNotFound'
        '500':
            $ref: '#/components/responses/InternalServerError'
    """

    room_id = request.match_info["room_id"]
    bot_mxid = request.query.get("bot_mxid", None)
    scopes = request.query.getall("scopes", ["room", "route"])
    response = {}

    try:
        room = await DBRoom.get_by_room_id(room_id)
        log.info(f"Room: {room}")
        if not room:
            return resp.not_found(f"room_id '{room_id}' not found")

        if not bot_mxid:
            bot_mxid = room._room_variables.get("current_bot_mxid")
            if not bot_mxid:
                return resp.not_found("current_bot_mxid not found in the room variables")

        route = await DBRoute.get_by_room_and_client(room=room.id, client=bot_mxid, create=False)
        if not route:
            return resp.not_found(f"Client '{bot_mxid}' not found in room")

        for scope in scopes:
            if scope == "room":
                response[scope] = room._room_variables
            elif scope == "route":
                response[scope] = route._variables
            else:
                log.warning(f"Invalid scope: {scope}, skipping")

    except Exception as e:
        return resp.server_error(str(e))

    return resp.ok(response) if response else resp.not_found("Scopes not found")
