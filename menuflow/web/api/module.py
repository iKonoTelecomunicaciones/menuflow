from __future__ import annotations

from json import JSONDecodeError
from logging import Logger, getLogger

from aiohttp import web

from ...config import Config
from ...db.flow import Flow as DBFlow
from ...db.module import Module as DBModule
from ..base import get_config, routes
from ..docs.module import (
    create_module_doc,
    delete_module_doc,
    get_module_doc,
    get_module_list_doc,
    update_module_doc,
)
from ..responses import resp
from ..util import Util

log: Logger = getLogger("menuflow.api.module")


@routes.get("/v1/{flow_id}/module", allow_head=False)
@Util.docstring(get_module_doc)
async def get_module(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Getting module")

    try:
        flow_id = int(request.match_info["flow_id"])

        if not await DBFlow.check_exists(flow_id):
            return resp.not_found(f"Flow with ID {flow_id} not found in the database", uuid)

    except (KeyError, ValueError):
        return resp.bad_request("Invalid or missing flow ID", uuid)
    except Exception as e:
        return resp.server_error(str(e), uuid)

    module_id = request.query.get("id", None)
    name = request.query.get("name", None)
    add_name = request.query.get("include_name_module", False)

    try:
        if module_id:
            module = await DBModule.get_by_id(int(module_id), flow_id)

            if not module:
                return resp.not_found(f"Module with ID {module_id} not found", uuid)
            data = module.serialize()
            if add_name:  # TODO: Temporary for adding module name to the response
                data = Util.parse_modules_for_module(data, module.name)

        elif name:
            module = await DBModule.get_by_name(name, flow_id)

            if not module:
                return resp.not_found(f"Module with name '{name}' not found", uuid)
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

    except Exception as e:
        return resp.server_error(str(e), uuid)

    return resp.ok(data, uuid)


@routes.post("/v1/{flow_id}/module")
@Util.docstring(create_module_doc)
async def create_module(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Creating new module")

    try:
        flow_id = int(request.match_info["flow_id"])
        data: dict = await request.json()

        if not data.get("name"):
            return resp.bad_request("Parameter 'name' is required", uuid)

        if not await DBFlow.check_exists(flow_id):
            return resp.not_found(f"Flow with ID {flow_id} not found in the database", uuid)

    except JSONDecodeError:
        return resp.body_not_json(uuid)
    except (KeyError, ValueError):
        return resp.bad_request("Invalid or missing flow ID", uuid)
    except Exception as e:
        return resp.server_error(str(e), uuid)

    name = data.get("name")
    if await DBModule.check_exists_by_name(name, flow_id):
        return resp.bad_request(
            f"Module with name '{name}' already exists in flow_id {flow_id}",
            uuid,
        )

    try:
        log.debug(f"({uuid}) -> Creating new module '{name}' in flow_id '{flow_id}'")
        new_module = DBModule(
            name=name,
            flow_id=flow_id,
            nodes=data.get("nodes", []),
            position=data.get("position", {}),
        )

        module_id = await new_module.insert()
    except Exception as e:
        return resp.server_error(str(e), uuid)

    return resp.created(
        {"detail": {"message": "Module created successfully", "data": {"module_id": module_id}}},
        uuid,
    )


@routes.patch("/v1/{flow_id}/module/{module_id}")
@Util.docstring(update_module_doc)
async def update_module(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Updating module")

    try:
        flow_id = int(request.match_info["flow_id"])
        module_id = int(request.match_info["module_id"])
        data: dict = await request.json()

        new_name = data.get("name")
        new_nodes = data.get("nodes")
        new_position = data.get("position")

        if not new_name and new_nodes is None and new_position is None:
            return resp.bad_request(
                "At least one of the parameters name, nodes or position is required", uuid
            )

        flow = await DBFlow.get_by_id(flow_id)

        if not flow:
            return resp.not_found(f"Flow with ID '{flow_id}' not found in the database", uuid)

        module = await DBModule.get_by_id(module_id, flow_id)

    except JSONDecodeError:
        return resp.body_not_json(uuid)
    except (KeyError, ValueError, TypeError):
        return resp.bad_request("Flow ID and module ID must be valid integers", uuid)
    except Exception as e:
        return resp.server_error(str(e), uuid)

    if not module:
        return resp.not_found(f"Module with ID {module_id} not found in flow_id {flow_id}", uuid)

    new_data = {}
    if new_name and new_name != module.name:
        if await DBModule.check_exists_by_name(new_name, flow_id, module_id):
            return resp.bad_request(
                f"Module with name '{new_name}' already exists in flow_id '{flow_id}'", uuid
            )
        new_data["name"] = new_name

    if new_nodes is not None and (new_nodes != module.nodes or new_nodes == []):
        new_data["nodes"] = new_nodes

    if new_position is not None and (new_position != module.position or new_position == {}):
        new_data["position"] = new_position

    if new_data:
        try:
            log.debug(f"({uuid}) -> Updating module '{module.name}' in flow_id '{flow_id}'")

            for key, value in new_data.items():
                setattr(module, key, value)

            await module.update()

            config: Config = get_config()
            if config["menuflow.load_flow_from"] == "database":
                modules = await DBModule.all(int(flow_id))
                nodes = [node for module in modules for node in module.get("nodes", [])]
                await Util.update_flow_db_clients(
                    flow_id, {"flow_variables": flow.flow_vars, "nodes": nodes}, config
                )
        except Exception as e:
            return resp.server_error(str(e), uuid)

    return resp.ok(
        {"detail": {"message": "Module updated successfully", "data": {"module_id": module_id}}},
        uuid,
    )


@routes.delete("/v1/{flow_id}/module/{module_id}")
@Util.docstring(delete_module_doc)
async def delete_module(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Deleting module")

    try:
        flow_id = int(request.match_info["flow_id"])
        module_id = int(request.match_info["module_id"])

        if not await DBFlow.check_exists(flow_id):
            return resp.not_found(f"Flow with ID '{flow_id}' not found in the database", uuid)

        module = await DBModule.get_by_id(module_id, flow_id)
        if not module:
            return resp.not_found(
                f"Module with ID {module_id} not found in flow_id {flow_id}", uuid
            )

        log.debug(f"({uuid}) -> Deleting module '{module.name}' in flow_id '{flow_id}'")
        await module.delete()

    except (KeyError, ValueError, TypeError):
        return resp.bad_request("Flow ID and module ID must be valid integers", uuid)
    except Exception as e:
        return resp.server_error(str(e), uuid)

    return resp.ok(
        {"detail": {"message": "Module deleted successfully", "data": {"module_id": module_id}}},
        uuid,
    )


@routes.get("/v1/{flow_id}/module/list", allow_head=False)
@Util.docstring(get_module_list_doc)
async def get_module_list(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Getting module list")

    fields = request.query.getall("fields", ["id", "name"])

    try:
        flow_id = int(request.match_info["flow_id"])

        if not await DBFlow.check_exists(flow_id):
            return resp.not_found(f"Flow with ID {flow_id} not found in the database", uuid)
    except (KeyError, ValueError):
        return resp.bad_request("Invalid or missing flow ID", uuid)
    except Exception as e:
        return resp.server_error(str(e), uuid)

    try:
        modules = {"modules": await DBModule.get_by_fields(flow_id, fields)}
    except Exception as e:
        return resp.server_error(str(e), uuid)

    return resp.ok(modules, uuid)
