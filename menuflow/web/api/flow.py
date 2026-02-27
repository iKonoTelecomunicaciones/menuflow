from __future__ import annotations

from json import JSONDecodeError
from logging import Logger, getLogger

from aiohttp import web

from ...config import Config
from ...db.flow import Flow as DBFlow
from ...db.flow_backup import FlowBackup
from ...db.module import Module as DBModule
from ...db.tag import Tag as DBTag
from ...repository.flow import Flow
from ..base import get_config, routes
from ..docs.flow import (
    create_or_update_flow_doc,
    get_flow_backups_doc,
    get_flow_doc,
    get_flow_nodes_doc,
    import_flow_doc,
    publish_flow_doc,
)
from ..responses import resp
from ..util import Util

log: Logger = getLogger("menuflow.api.flow")


# Update or create new flow
@routes.put("/v1/flow")
@Util.docstring(create_or_update_flow_doc)
async def create_or_update_flow(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Creating or updating flow")

    config: Config = get_config()
    try:
        data: dict = await request.json()
    except JSONDecodeError:
        return resp.body_not_json(uuid)

    flow_id = data.get("id")
    incoming_flow = data.get("flow", {})
    flow_vars = data.get("flow_vars")

    if not incoming_flow and flow_vars is None:
        return resp.bad_request("Parameter flow or flow_vars is required", uuid)

    variables = (
        incoming_flow.get("menu", {}).get("flow_variables", {})
        if incoming_flow
        else flow_vars or {}
    )

    nodes, positions = Util.parse_flow_to_module_fmt(incoming_flow)

    if flow_id:
        flow = await DBFlow.get_by_id(flow_id)
        if not flow:
            return resp.not_found(f"Flow with ID {flow_id} not found", uuid)

        current_tag = await DBTag.get_current_tag(int(flow_id))
        if not current_tag:
            return resp.not_found(f"Current tag not found for flow {flow_id}", uuid)

        await Flow.update_flow(
            flow,
            incoming_flow,
            variables,
            nodes,
            positions,
            current_tag,
        )

        # Create backup if requested and flow changed
        if flow.flow and incoming_flow:
            await flow.backup_flow(config)

        if config["menuflow.load_flow_from"] == "database":
            modules = await DBModule.all(int(flow_id))
            nodes = [node for module in modules for node in module.get("nodes", [])]
            await Util.update_flow_db_clients(
                flow_id, {"flow_variables": variables, "nodes": nodes}, config, uuid
            )

        message = "Flow updated successfully"
    else:
        new_flow = DBFlow(flow=incoming_flow, flow_vars=variables)
        flow_id = await new_flow.insert()

        # Create a current tag for the new flow
        current_tag = DBTag(
            flow_id=flow_id, name="current", flow_vars=variables, author="system", active=True
        )
        tag_id = await current_tag.insert()

        if incoming_flow:
            for name, node in nodes.items():
                module_obj = DBModule(
                    flow_id=flow_id,
                    name=name,
                    nodes=node.get("nodes", []),
                    position=positions.get(name, {}),
                    tag_id=tag_id,
                )
                await module_obj.insert()

        message = "Flow created successfully"

    return resp.ok({"detail": {"message": message, "data": {"flow_id": flow_id}}}, uuid)


@routes.get("/v1/flow", allow_head=False)
@Util.docstring(get_flow_doc)
async def get_flow(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Getting flow")

    flow_id = request.query.get("id", None)
    client_mxid = request.query.get("client_mxid", None)
    flow_format = request.query.get(
        "flow_format", False
    )  # TODO: Remove this after a stable release of modules

    if flow_id or client_mxid:
        if flow_id:
            flow = await DBFlow.get_by_id(int(flow_id))
            if not flow:
                return resp.not_found(f"Flow with ID {flow_id} not found", uuid)
        else:
            flow = await DBFlow.get_by_mxid(client_mxid)
            if not flow:
                return resp.not_found(f"Flow with mxid {client_mxid} not found", uuid)
            flow_id = flow.id

        # Get the current tag for this flow
        current_tag = await DBTag.get_current_tag(int(flow_id))
        modules = await DBModule.get_tag_modules(current_tag.id)

        if not flow_format and modules or flow.flow == {}:
            log.debug(f"({uuid}) -> New flow format detected, parsing modules to flow format")
            nodes, positions = Util.parse_module_to_flow_fmt(modules)
            data = {
                "id": flow.id,
                "flow": {
                    "menu": {
                        "flow_variables": current_tag.flow_vars,
                        "nodes": nodes,
                    },
                    "modules": positions,
                },
                "flow_vars": current_tag.flow_vars,
            }
        else:  # TODO: This is a temporary solution to return the flow when they are not yet in the module table
            log.warning(f"({uuid}) -> Old flow format detected, returning flow from column")
            data = flow.serialize()
            data["flow_vars"] = flow.get("flow", {}).get("menu", {}).get("flow_variables", {})

        log_msg = f"Returning flow_id: {flow_id} with {len(data['flow']['menu']['nodes'])} nodes"

    else:
        flows = await DBFlow.all()
        if flow_format:
            for flow in flows:
                flow["flow_vars"] = flow.get("flow", {}).get("menu", {}).get("flow_variables", {})
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
                            "flow_vars": flow.get("flow_vars", {}),
                        }
                    )
                else:  # TODO: This is a temporary solution to return the flow when they are not yet in the module table
                    flow["flow_vars"] = (
                        flow.get("flow", {}).get("menu", {}).get("flow_variables", {})
                    )
                    list_flows.append(flow)

            data = {"flows": list_flows}

        log_msg = f"Returning {len(data['flows'])} flows"

    return resp.success(data=data, uuid=uuid, log_msg=log_msg)


@routes.get("/v1/flow/{flow_identifier}/nodes", allow_head=False)
@Util.docstring(get_flow_nodes_doc)
async def get_flow_nodes(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Getting flow nodes")

    flow_identifier = request.match_info["flow_identifier"]

    flow_format = request.query.get(
        "flow_format", False
    )  # TODO: Remove this after a stable release of modules
    filters_nodes = request.query.getall("filters_nodes", ["id", "type", "name"])

    flow = (
        await DBFlow.get_by_id(int(flow_identifier))
        if flow_identifier.isdigit()
        else await DBFlow.get_by_mxid(flow_identifier)
    )

    if not flow:
        return resp.not_found(f"Flow with identifier {flow_identifier} not found", uuid)

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

    log_msg = f"Returning {len(list_nodes)} nodes for flow {flow_id}"
    return resp.success(data={"id": flow.id, "nodes": list_nodes}, uuid=uuid, log_msg=log_msg)


@routes.get("/v1/flow/{flow_id}/backup", allow_head=False)
@Util.docstring(get_flow_backups_doc)
async def get_backup(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Getting flow backups")

    offset = int(request.query.get("offset", 0))
    limit = int(request.query.get("limit", 10))
    backup_id = request.query.get("backup_id", None)

    flow_id = int(request.match_info["flow_id"])
    flow = await DBFlow.get_by_id(int(flow_id))
    if not flow:
        return resp.not_found(f"Flow with ID {flow_id} not found", uuid)

    if backup_id:
        backup = await FlowBackup.get_by_id(int(backup_id))
        if not backup:
            return resp.not_found(f"Backup with ID {backup_id} not found", uuid)
        return resp.ok(backup.to_dict(), uuid)

    count = await FlowBackup.get_count_by_flow_id(flow_id=flow_id)
    backups = await FlowBackup.all_by_flow_id(flow_id=flow_id, offset=offset, limit=limit)

    return resp.success(
        data={"count": count, "backups": [backup.to_dict() for backup in backups]},
        uuid=uuid,
        log_msg=f"Returning {count} backups for flow {flow_id}",
    )


@routes.post("/v1/flow/{flow_id}/publish")
@Util.docstring(publish_flow_doc)
async def publish_flow(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Publishing flow")

    try:
        flow_id = int(request.match_info["flow_id"])
    except ValueError:
        return resp.bad_request("Flow ID must be an integer", uuid)

    flow = await DBFlow.get_by_id(flow_id)
    if not flow:
        return resp.not_found(f"Flow with ID {flow_id} not found", uuid)

    try:
        data = await request.json()
    except JSONDecodeError:
        return resp.not_found("Invalid JSON in request body", uuid)

    name = data.get("name")
    author = data.get("author")

    if not name or not author:
        return resp.bad_request("Parameters 'name' and 'author' are required", uuid)

    log.debug(f"({uuid}) -> creating new tag '{name}' for flow ID {flow_id}")

    current_tag = await DBModule.get_current_tag(flow_id)
    if not current_tag:
        return resp.not_found(f"No current tag found for flow ID {flow_id}", uuid)

    log.debug(f"({uuid}) -> Found current tag with ID for flow {flow_id}: {current_tag["id"]}")

    new_tag = DBTag(
        flow_id=flow_id,
        name=name,
        author=author,
        flow_vars=current_tag["flow_vars"],
        active=False,
    )
    tag_id = await new_tag.insert()

    log.debug(f"({uuid}) -> New tag created for flow {flow_id} with ID {tag_id}")

    result = await DBModule.copy_modules_from_tag(current_tag["id"], tag_id)
    if not result.get("success"):
        return resp.internal_error(f"Error copying modules: {result.get('error')}", uuid)

    await DBTag.deactivate_tags(flow_id)
    await DBTag.activate_tag(tag_id)

    config: Config = get_config()
    if config["menuflow.load_flow_from"] == "database":
        modules = await DBModule.get_tag_modules(int(tag_id))
        flow_vars = await DBTag.get_by_id(tag_id)
        nodes = [node for module in modules for node in module.get("nodes", [])]
        await Util.update_flow_db_clients(
            flow_id, {"flow_variables": flow_vars.flow_vars, "nodes": nodes}, config, uuid
        )

    return resp.ok(
        {
            "detail": {
                "message": f"Flow published successfully with tag '{name}'",
            }
        },
        uuid,
    )


# Import flow
@routes.put("/v1/flow/import")
@Util.docstring(import_flow_doc)
async def import_flow(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Importing flow")

    config: Config = get_config()
    try:
        data: dict = await request.json()
    except JSONDecodeError:
        return resp.body_not_json(uuid)

    flow_id = data.get("id")
    incoming_flow = data.get("flow", {})
    flow_vars = data.get("flow_vars")

    if not incoming_flow and flow_vars is None:
        return resp.bad_request("Parameter flow or flow_vars is required", uuid)

    if not flow_id:
        return resp.bad_request("Parameter 'id' is required for import", uuid)

    variables = (
        incoming_flow.get("menu", {}).get("flow_variables", {})
        if incoming_flow
        else flow_vars or {}
    )

    nodes, positions = Util.parse_flow_to_module_fmt(incoming_flow)

    flow = await DBFlow.get_by_id(flow_id)
    if not flow:
        return resp.not_found(f"Flow with ID {flow_id} not found", uuid)

    current_tag = await DBTag.get_current_tag(int(flow_id))
    if not current_tag:
        return resp.not_found(f"Current tag not found for flow {flow_id}", uuid)

    await Flow.update_flow(flow, incoming_flow, variables, nodes, positions, current_tag)

    return resp.ok(
        {"detail": {"message": "Flow imported successfully", "data": {"flow_id": flow_id}}}, uuid
    )
