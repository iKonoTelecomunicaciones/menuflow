from __future__ import annotations

from json import JSONDecodeError
from logging import Logger, getLogger
from typing import Dict

from aiohttp import web

from ...db.module import Module as DBModule
from ..base import routes
from ..docs.module import create_module_doc, delete_module_doc, get_module_doc, update_module_doc
from ..responses import resp
from ..util import Util

log: Logger = getLogger("menuflow.api.module")


def docstring(doc: str):
    """Decorator to add docstring to a function.

    Parameters
    ----------
    doc: str
        The docstring to add to the function.
    Returns
    -------
    function
        The function with the docstring added.
    """

    def wrapper(func):
        func.__doc__ = doc
        return func

    return wrapper


@routes.get("/v1/{flow_id}/module", allow_head=False)
@docstring(get_module_doc)
async def get_module(request: web.Request) -> web.Response:
    flow_id = int(request.match_info["flow_id"])

    if not flow_id:
        return resp.bad_request("Flow ID is required")

    module_id = request.query.get("id", None)
    name = request.query.get("name", None)
    add_name = request.query.get("include_name_module", False)

    if module_id:
        module = await DBModule.get_by_id(int(module_id), flow_id)
        if not module:
            return resp.not_found(f"Module with ID {module_id} not found")
        data = module.serialize()
        if add_name:  # TODO: Temporary for adding module name to the response
            data = Util.parse_modules_for_module(data, module.name)
    elif name:
        module = await DBModule.get_by_name(name, flow_id)
        if not module:
            return resp.not_found(f"Module with name '{name}' not found")
        data = module.serialize()
        if add_name:  # TODO: Temporary for adding module name to the response
            data = Util.parse_modules_for_module(data, name)
    else:
        modules = [module.serialize() for module in await DBModule.all(flow_id)]
        if not add_name:
            data = {"modules": {module.pop("name"): module for module in modules}}
        else:  # TODO: Temporary for adding module name to the response
            response = {}
            for module in modules:
                data_dict = Util.parse_modules_for_module(module, module.get("name"))
                response[data_dict.pop("name")] = data_dict
            data = {"modules": response}

    return resp.ok(data)


@routes.post("/v1/{flow_id}/module")
@docstring(create_module_doc)
async def create_module(request: web.Request) -> web.Response:
    flow_id = int(request.match_info["flow_id"])

    if not flow_id:
        return resp.bad_request("Flow ID is required")

    try:
        data: Dict = await request.json()
    except JSONDecodeError:
        return resp.body_not_json

    if not data.get("name"):
        return resp.bad_request("Parameter 'name' is required")

    if await DBModule.check_exists_by_name(data["name"], flow_id, module_id=None):
        return resp.bad_request(
            f"Module with name '{data['name']}' already exists in flow_id {flow_id}"
        )

    new_module = DBModule(
        name=data["name"],
        flow_id=flow_id,
        nodes=data.get("nodes", []),
        position=data.get("position", {}),
    )

    log.debug(f"Creating new module: {new_module.__dict__}")

    module_id = await new_module.insert()

    return resp.ok(
        {"detail": {"message": "Module created successfully", "data": {"module_id": module_id}}}
    )


@routes.patch("/v1/{flow_id}/module/{module_id}")
@docstring(update_module_doc)
async def update_module(request: web.Request) -> web.Response:
    try:
        flow_id = int(request.match_info["flow_id"])
        module_id = int(request.match_info["module_id"])
    except (KeyError, ValueError, TypeError):
        return resp.bad_request("Flow ID and module ID must be valid integers")
    else:
        if not flow_id or not module_id:
            return resp.bad_request("Flow ID and module ID are required")

    module = await DBModule.get_by_id(module_id, flow_id)
    if not module:
        return resp.not_found(f"Module with ID {module_id} not found in flow_id {flow_id}")

    try:
        data: Dict = await request.json()
    except JSONDecodeError:
        return resp.body_not_json

    if not data.get("name") and not data.get("nodes") and not data.get("position"):
        return resp.bad_request(
            "At least one of the parameters name, nodes or position is required"
        )

    new_name = data.get("name")
    if new_name and new_name != module.name:
        if await DBModule.check_exists_by_name(new_name, flow_id, module_id):
            return resp.bad_request(
                f"Module with name '{new_name}' already exists in flow_id {flow_id}"
            )
        module.name = new_name

    new_nodes = data.get("nodes")
    if new_nodes and new_nodes != module.nodes or new_nodes == []:
        module.nodes = new_nodes

    new_position = data.get("position")
    if new_position and new_position != module.position or new_position == {}:
        module.position = new_position

    await module.update()

    return resp.ok(
        {"detail": {"message": "Module updated successfully", "data": {"module_id": module_id}}}
    )


@routes.delete("/v1/{flow_id}/module/{module_id}")
@docstring(delete_module_doc)
async def delete_module(request: web.Request) -> web.Response:
    try:
        flow_id = int(request.match_info["flow_id"])
        module_id = int(request.match_info["module_id"])
    except (KeyError, ValueError, TypeError):
        return resp.bad_request("Flow ID and module ID must be valid integers")
    else:
        if not flow_id or not module_id:
            return resp.bad_request("Flow ID and module ID are required")

    module = await DBModule.get_by_id(module_id, flow_id)
    if not module:
        return resp.not_found(f"Module with ID {module_id} not found in flow_id {flow_id}")

    await module.delete()

    return resp.ok(
        {"detail": {"message": "Module deleted successfully", "data": {"module_id": module_id}}}
    )
