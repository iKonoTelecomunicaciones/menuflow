from __future__ import annotations

from json import JSONDecodeError
from typing import Dict

from aiohttp import web

from ...config import Config
from ...db.client import Client as DBClient
from ...db.flow import Flow as DBFlow
from ...menu import MenuClient
from ..base import get_config, routes
from ..responses import resp


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
        data: Dict = await request.json()
    except JSONDecodeError:
        return resp.body_not_json

    flow_id = data.get("id", None)
    incoming_flow = data.get("flow", None)

    if not incoming_flow:
        return resp.bad_request("Parameter flow is required")

    if flow_id:
        flow = await DBFlow.get_by_id(flow_id)
        flow.flow = incoming_flow
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
        new_flow = DBFlow(flow=incoming_flow)
        await new_flow.insert()
        message = "Flow created successfully"

    flow_id_response = new_flow.id if not flow_id else flow_id
    return resp.ok({"detail": {"message": message, "data": {"id": flow_id_response}}})


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

    responses:
        '200':
            $ref: '#/components/responses/GetFlowSuccess'
        '404':
            $ref: '#/components/responses/GetFlowNotFound'
    """
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
