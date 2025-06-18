from __future__ import annotations

from json import JSONDecodeError
from logging import Logger, getLogger

from aiohttp import web

from ...config import Config
from ...db.client import Client as DBClient
from ...db.flow import Flow as DBFlow
from ...db.flow_backup import FlowBackup
from ...db.module import Module as DBModule
from ...menu import MenuClient
from ..base import get_config, routes
from ..responses import resp
from ..util import Util

log: Logger = getLogger("menuflow.api.flow")


# Update or create new flow
@routes.put("/v1/flow")
async def create_or_update_flow(request: web.Request) -> web.Response:
    """
    ---
    summary: Creates a new flow or update it if exists.
    tags:
        - Flow

    requestBody:
        required: false
        description: A json with `id` and `flow` keys.
                     `id` is the flow ID to update, `flow` is the flow content.
        content:
            application/json:
                schema:
                    type: object
                    properties:
                        id:
                            type: integer
                        flow:
                            type: object
                    required:
                        - flow
                    example:
                        id: 1
                        flow:
                            menu:
                                flow_variables:
                                    var1: "value1"
                                    var2: "value2"
                                nodes:
                                    - id: 1
                                      type: "message"
                                      content: "Hello"
                                      o_connection: 2
    responses:
        '200':
            $ref: '#/components/responses/CreateUpdateFlowSuccess'
        '400':
            $ref: '#/components/responses/CreateUpdateFlowBadRequest'
    """
    config: Config = get_config()
    try:
        data: dict = await request.json()
    except JSONDecodeError:
        return resp.body_not_json

    flow_id = data.get("id", None)
    incoming_flow = data.get("flow", None)

    if not incoming_flow:
        return resp.bad_request("Parameter flow is required")

    flow_vars = incoming_flow.get("menu", {}).get("flow_variables", {})
    nodes, positions = Util.parse_flow_to_module_fmt(incoming_flow)

    if flow_id:
        flow = await DBFlow.get_by_id(flow_id)
        if not flow:
            return resp.not_found(f"Flow with ID {flow_id} not found")

        modules = await DBModule.all(int(flow_id))

        if modules:
            for module_obj in modules:
                name = module_obj.name
                if name not in nodes:
                    await module_obj.delete()
                else:
                    new_nodes = nodes.get(name, {}).get("nodes", [])
                    if module_obj.nodes != new_nodes:
                        module_obj.nodes = new_nodes
                    nodes.pop(name, None)

                    new_position = positions.pop(name, {})
                    if module_obj.position != new_position:
                        module_obj.position = new_position

                    await module_obj.update()

        for name, node in nodes.items():
            module_obj = DBModule(
                flow_id=flow_id,
                name=name,
                nodes=node.get("nodes", []),
                position=positions.get(name, {}),
            )
            await module_obj.insert()

        if flow.flow != incoming_flow:
            await flow.backup_flow(config)

        flow.flow = incoming_flow
        flow.flow_vars = flow_vars
        await flow.update()

        if config["menuflow.load_flow_from"] == "database":
            db_clients = await DBClient.get_by_flow_id(flow_id)
            for db_client in db_clients:
                client = MenuClient.cache[db_client.id]
                config: Config = get_config()
                await client.flow_cls.load_flow(
                    flow_mxid=client.id, content=incoming_flow, config=config
                )
        message = "Flow updated successfully"
    else:
        new_flow = DBFlow(flow=incoming_flow, flow_vars=flow_vars)
        flow_id = await new_flow.insert()

        for name, node in nodes.items():
            module_obj = DBModule(
                flow_id=flow_id,
                name=name,
                nodes=node.get("nodes", []),
                position=positions.get(name, {}),
            )
            await module_obj.insert()

        message = "Flow created successfully"

    return resp.ok({"detail": {"message": message, "data": {"flow_id": flow_id}}})


@routes.get("/v1/flow", allow_head=False)
async def get_flow(request: web.Request) -> web.Response:
    """
    ---
    summary: Get flow by ID or client MXID.
    tags:
        - Flow

    parameters:
        - in: query
          name: id
          schema:
            type: integer
          description: The flow ID to get.
        - in: query
          name: client_mxid
          schema:
            type: string
          description: The client MXID to get the flow.
        - in: query
          name: flow_format
          schema:
            type: boolean
            default: false
          description: Return the old flow format.

    responses:
        '200':
            $ref: '#/components/responses/GetFlowSuccess'
        '404':
            $ref: '#/components/responses/GetFlowNotFound'
    """
    flow_id = request.query.get("id", None)
    client_mxid = request.query.get("client_mxid", None)
    flow_format = request.query.get(
        "flow_format", False
    )  # TODO: Remove this after a stable release of modules

    if flow_id or client_mxid:
        if flow_id:
            flow = await DBFlow.get_by_id(int(flow_id))
            if not flow:
                return resp.not_found(f"Flow with ID {flow_id} not found")
        else:
            flow = await DBFlow.get_by_mxid(client_mxid)
            if not flow:
                return resp.not_found(f"Flow with mxid {client_mxid} not found")
            flow_id = flow.id

        modules = await DBModule.all(int(flow_id))

        if not flow_format and modules:
            nodes, positions = Util.parse_module_to_flow_fmt(modules)
            data = {
                "id": flow.id,
                "flow": {
                    "menu": {
                        "flow_variables": flow.flow_vars,
                        "nodes": nodes,
                    },
                    "modules": positions,
                },
            }
        else:  # TODO: This is a temporary solution to return the flow when they are not yet in the module table
            data = flow.serialize()
            data.pop("flow_vars")

    else:
        flows = await DBFlow.all()
        if flow_format:
            data = {"flows": flows}
        else:
            list_flows = []
            for flow in flows:
                modules = [module.serialize() for module in await DBModule.all(flow.get("id"))]
                if modules:
                    nodes, positions = Util.parse_module_to_flow_fmt(modules)
                    list_flows.append(
                        {
                            "id": flow.get("id"),
                            "flow": {
                                "menu": {
                                    "flow_variables": flow.get("flow_vars", {}),
                                    "nodes": nodes,
                                },
                                "modules": positions,
                            },
                        }
                    )
                else:  # TODO: This is a temporary solution to return the flow when they are not yet in the module table
                    flow.pop("flow_vars")
                    list_flows.append(flow)

            data = {"flows": list_flows}

    return resp.ok(data)


@routes.get("/v1/flow/{flow_identifier}/nodes", allow_head=False)
async def get_flow_nodes(request: web.Request) -> web.Response:
    """
    ---
    summary: Get flow nodes by ID or client MXID
    tags:
        - Flow

    parameters:
        - in: path
          name: flow_identifier
          schema:
            type: string
          required: true
          description: The flow identifier to obtain can be `id` or `mxid`.
        - in: query
          name: flow_format
          schema:
            type: boolean
            default: false
          description: Return the old flow format.
        - in: query
          name: filters_nodes
          schema:
            type: array
            default: ["id", "type", "name"]
            items:
              type: string
          description: List of nodes to filter.

    responses:
        '200':
            $ref: '#/components/responses/GetFlowNodesSuccess'
        '404':
            $ref: '#/components/responses/GetFlowNotFound'
    """
    flow_identifier = request.match_info["flow_identifier"]

    try:
        flow_identifier = int(flow_identifier)
    except Exception as e:
        pass

    flow_format = request.query.get(
        "flow_format", False
    )  # TODO: Remove this after a stable release of modules
    filters_nodes = request.query.getall("filters_nodes", ["id", "type", "name"])

    if isinstance(flow_identifier, int):
        flow = await DBFlow.get_by_id(flow_identifier)
        if not flow:
            return resp.not_found(f"Flow with ID {flow_identifier} not found")
    else:
        flow = await DBFlow.get_by_mxid(flow_identifier)
        if not flow:
            return resp.not_found(f"Flow with mxid {flow_identifier} not found")

    flow_id = flow.id
    modules = await DBModule.all(int(flow_id))
    list_nodes = []

    if not flow_format and modules:
        for module in modules:
            list_nodes.extend(Util.filter_nodes_by_keys(module.nodes, filters_nodes))
    else:  # TODO: This is a temporary solution to return the flow when they are not yet in the module table
        data = flow.serialize()
        nodes = data.get("flow", {}).get("menu", {}).get("nodes", [])
        list_nodes.extend(Util.filter_nodes_by_keys(nodes, filters_nodes))

    return resp.ok({"id": flow.id, "nodes": list_nodes})


@routes.get("/v1/flow/{flow_id}/backup", allow_head=False)
async def get_backup(request: web.Request) -> web.Response:
    """
    ---
    summary: Get flow backups by flow ID.
    tags:
        - Flow

    parameters:
        - in: path
          name: flow_id
          description: The flow ID to get the backups.
          required: true
          schema:
            type: integer

        - in: query
          name: limit
          description: The limit of backups to get.
          schema:
            type: integer

        - in: query
          name: offset
          description: The offset of backups to get.
          schema:
            type: integer

        - in: query
          name: backup_id
          description: The backup ID to get.
          schema:
              type: integer

    responses:
        '200':
            $ref: '#/components/responses/GetFlowBackupsSuccess'
        '404':
            $ref: '#/components/responses/GetFlowBackupsNotFound'

    """
    offset = int(request.query.get("offset", 0))
    limit = int(request.query.get("limit", 10))
    backup_id = request.query.get("backup_id", None)

    flow_id = int(request.match_info["flow_id"])
    flow = await DBFlow.get_by_id(int(flow_id))
    if not flow:
        return resp.not_found(f"Flow with ID {flow_id} not found")

    if backup_id:
        backup = await FlowBackup.get_by_id(int(backup_id))
        if not backup:
            return resp.not_found(f"Backup with ID {backup_id} not found")
        return resp.ok(backup.to_dict())

    count = await FlowBackup.get_count_by_flow_id(flow_id=flow_id)
    backups = await FlowBackup.all_by_flow_id(flow_id=flow_id, offset=offset, limit=limit)
    return resp.ok({"count": count, "backups": [backup.to_dict() for backup in backups]})
