from __future__ import annotations

from logging import Logger, getLogger

from aiohttp import web

from ...db.flow import Flow as DBFlow
from ...db.module import Module as DBModule
from ...db.tag import Tag as DBTag
from ...utils import convert_to_bool
from ..base import routes
from ..docs.node import get_node_doc, get_node_list_doc
from ..responses import resp
from ..util import Util as UtilWeb

log: Logger = getLogger("menuflow.api.node")


@routes.get("/v1/{flow_id}/node/{id}", allow_head=False)
@UtilWeb.docstring(get_node_doc)
async def get_node(request: web.Request) -> web.Response:
    uuid = UtilWeb.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Getting node")

    add_module_name = convert_to_bool(request.query.get("add_module_name", True))
    node_id = request.match_info["id"]

    try:
        flow_id = int(request.match_info["flow_id"])

        if not await DBFlow.check_exists(flow_id):
            return resp.not_found(f"Flow with ID {flow_id} not found in the database", uuid)

        node = await DBModule.get_node_by_id(flow_id, node_id, add_module_name)
    except (KeyError, ValueError):
        return resp.bad_request("Invalid or missing flow ID", uuid)
    except Exception as e:
        return resp.server_error(str(e), uuid)

    if not node:
        return resp.not_found(f"Node with ID '{node_id}' not found in the database", uuid)

    return resp.ok(node, uuid)


@routes.get("/v1/{flow_id}/node", allow_head=False)
@UtilWeb.docstring(get_node_list_doc)
async def get_node_list(request: web.Request) -> web.Response:
    uuid = UtilWeb.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Getting node list")

    module_fields = request.query.getall("module_fields", ["id"])
    node_fields = request.query.getall("node_fields", ["id", "name", "type"])

    try:
        flow_id = int(request.match_info["flow_id"])

        if not await DBFlow.check_exists(flow_id):
            return resp.not_found(f"Flow with ID {flow_id} not found in the database", uuid)

        current_tag = await DBTag.get_current_tag(int(flow_id))
        modules = await DBModule.get_tag_modules(int(current_tag.id))

        node_list = []
        for module in modules:
            module_data = {f"module_{field}": getattr(module, field) for field in module_fields}
            node_list.extend(
                {
                    **module_data,
                    **{node_field: node.get(node_field) for node_field in node_fields},
                }
                for node in module.nodes
            )

    except (KeyError, ValueError):
        return resp.bad_request("Invalid or missing flow ID", uuid)
    except Exception as e:
        return resp.server_error(str(e), uuid)

    return resp.ok({"nodes": node_list}, uuid)
