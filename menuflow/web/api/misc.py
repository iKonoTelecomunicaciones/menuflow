from __future__ import annotations

import asyncio
import traceback
from asyncio import all_tasks
from logging import Logger, getLogger

import yaml
from aiohttp import web
from jinja2.exceptions import TemplateSyntaxError, UndefinedError

from ...config import Config
from ...db.flow import Flow as DBFlow
from ...db.room import Room as DBRoom
from ...db.route import Route as DBRoute
from ...flow_utils import FlowUtils
from ...jinja.env import jinja_env
from ...utils.errors import GettingDataError
from ...utils.flags import RenderFlags
from ...utils.util import Util as Utils
from ..base import get_config, get_flow_utils, routes
from ..docs.misc import (
    check_jinja_template_doc,
    get_countries_doc,
    get_email_servers_doc,
    get_middlewares_doc,
    get_task_doc,
    render_data_doc,
)
from ..responses import resp
from ..util import Util as UtilWeb

log: Logger = getLogger("menuflow.api.misc")


@routes.get("/v1/mis/email_servers", allow_head=False)
@UtilWeb.docstring(get_email_servers_doc)
async def get_id_email_servers(request: web.Request) -> web.Response:
    trace_id = UtilWeb.generate_uuid()
    log.info(f"({trace_id}) -> '{request.method}' '{request.path}' Getting email servers")

    data = {"email_servers": list(FlowUtils.email_servers_by_id.keys())}
    return resp.success(data=data, uuid=trace_id)


@routes.get("/v1/mis/middlewares", allow_head=False)
@UtilWeb.docstring(get_middlewares_doc)
async def get_id_middlewares(request: web.Request) -> web.Response:
    trace_id = UtilWeb.generate_uuid()
    log.info(f"({trace_id}) -> '{request.method}' '{request.path}' Getting middlewares")

    flow_utils = get_flow_utils()
    middlewares = [
        {"id": middleware.id, "type": middleware.type}
        for middleware in flow_utils.data.middlewares
    ]
    return resp.success(data={"middlewares": middlewares}, uuid=trace_id)


@routes.post("/v1/mis/check_template")
@UtilWeb.docstring(check_jinja_template_doc)
async def check_jinja_template(request: web.Request) -> web.Response:
    trace_id = UtilWeb.generate_uuid()
    log.info(f"({trace_id}) -> '{request.method}' '{request.path}' Checking jinja template")
    dict_variables = {}

    try:
        data = await request.post()
    except Exception as e:
        return resp.bad_request(f"Error reading data: {e}", trace_id)

    template = data.get("template")
    variables = data.get("variables")

    log.info(f"({trace_id}) -> Checking jinja template with data: {data}")

    if not template:
        return resp.bad_request("Template is required", trace_id)

    if variables:
        try:
            dict_variables = yaml.safe_load(variables)
        except Exception as e:
            log.exception(e)
            return resp.bad_request(f"Error format variables: {e}", trace_id)
        else:
            if not isinstance(dict_variables, dict):
                return resp.bad_request("The format of the variables is not valid", trace_id)
    try:
        template = jinja_env.from_string(template)
        rendered_data = template.render(**dict_variables) if variables else template.render()
    except TemplateSyntaxError as e:
        log.exception(e)
        return resp.unprocessable_entity(
            f"func_name: {e.name}, \nfilename: {e.filename if e.filename else '<template>'}, \nline: {e.lineno}, \nerror: {e.message}",
            trace_id,
        )
    except UndefinedError as e:
        log.exception(e)
        tb_list = traceback.extract_tb(e.__traceback__)
        traceback_info = tb_list[-1]

        func_name = traceback_info.name
        filename = traceback_info.filename
        line = traceback_info.lineno

        return resp.unprocessable_entity(
            f"func_name: {func_name}, \nfilename: {filename}, \nline: {line}, \nerror: {e}",
            trace_id,
        )
    except Exception as e:
        log.exception(e)
        return resp.bad_request(str(e), trace_id)

    return resp.success(message="Data rendered", data=rendered_data, uuid=trace_id)


@routes.post("/v1/mis/render_data")
@UtilWeb.docstring(render_data_doc)
async def render_data(request: web.Request) -> web.Response:
    trace_id = UtilWeb.generate_uuid()
    log.info(f"({trace_id}) -> '{request.method}' '{request.path}' Rendering data")

    try:
        data = await request.post()
    except Exception as e:
        return resp.bad_request(f"Error reading data: {e}", trace_id)

    template = data.get("template")
    variables = data.get("variables")
    room_id = data.get("room_id")
    string_format = data.get("string_format", False)
    flags = data.get(
        "flags",
        {
            "REMOVE_QUOTES": True,
            "LITERAL_EVAL": True,
            "CONVERT_TO_TYPE": True,
            "CUSTOM_ESCAPE": False,
        },
    )

    try:
        flags = yaml.safe_load(flags)
    except Exception as e:
        pass
    finally:
        if not isinstance(flags, dict):
            return resp.bad_request("The format of the flags is not valid", trace_id)

    _flags = RenderFlags.RETURN_ERRORS
    for flag, enabled in flags.items():
        if enabled is True:
            _flags |= getattr(RenderFlags, flag)

    log.info(f"({trace_id}) -> Checking jinja template with data: {data}")

    if not template:
        return resp.bad_request("Template is required", trace_id)

    dict_variables = {}

    if room_id:
        room_obj = await DBRoom.get_by_room_id(room_id)
        if not room_obj:
            return resp.not_found(f"Room '{room_id}' not found")
        else:
            bot_mxid = room_obj._variables.get("current_bot_mxid")

            if room_obj and bot_mxid:
                route_obj = await DBRoute.get_by_room_and_client(
                    room=room_obj.id, client=bot_mxid, create=False
                )
                flow_obj = await DBFlow.get_by_mxid(bot_mxid)

                if room_obj._variables:
                    dict_variables |= {"room": room_obj._variables}

                if route_obj.variables:
                    dict_variables |= {"route": route_obj._variables}

                if route_obj.node_vars:
                    dict_variables |= {"node": route_obj._node_vars}

                if flow_obj.flow_vars:
                    dict_variables |= {"flow": flow_obj.flow_vars}

    if variables:
        try:
            dict_variables |= yaml.safe_load(variables)
        except Exception as e:
            log.exception(e)
            return resp.bad_request(f"Error format variables: {e}", trace_id)
        else:
            if not isinstance(dict_variables, dict):
                return resp.bad_request("The format of the variables is not valid", trace_id)

    try:
        if RenderFlags.CUSTOM_ESCAPE in _flags:
            dict_variables, changed = Utils.custom_escape(dict_variables, escape=False)
            _flags = _flags | RenderFlags.CUSTOM_UNESCAPE if changed else _flags

        new_render_data = Utils.recursive_render(template, dict_variables, flags=_flags)
    except Exception as e:
        return resp.server_error(str(e), trace_id)

    response = {
        "rendered": new_render_data,
        **({"string_format": str(new_render_data)} if string_format else {}),
    }

    if old_render:
        try:
            old_render_data = Utils.old_render_data(template, dict_variables)
        except Exception as e:
            old_render_data = str(e)

        response.update(
            {"old_render_data": old_render_data, "equal": new_render_data == old_render_data}
        )

    return resp.success(data=response, uuid=trace_id)


@routes.get("/v1/mis/countries", allow_head=False)
@UtilWeb.docstring(get_countries_doc)
async def countries(request: web.Request) -> web.Response:
    trace_id = UtilWeb.generate_uuid()
    log.info(f"({trace_id}) -> '{request.method}' '{request.path}' Getting countries")

    config: Config = get_config()
    language = request.query.get("language", "es")

    try:
        countries = await Utils(config=config).get_countries(language)
    except GettingDataError as e:
        return resp.server_error(f"Error getting countries: {e}")

    return resp.success(data=countries, uuid=trace_id)


@routes.get("/v1/mis/get_task", allow_head=False)
@UtilWeb.docstring(get_task_doc)
async def get_task(request: web.Request) -> web.Response:
    trace_id = UtilWeb.generate_uuid()
    log.info(f"({trace_id}) -> '{request.method}' '{request.path}' Getting tasks")

    name = request.query.get("name")
    if name:
        tasks = all_tasks()
        tasks = [task for task in tasks if name in task.get_name()]
        if not tasks:
            return resp.not_found(f"No tasks found with name '{name}'", trace_id)
    else:
        tasks = asyncio.all_tasks()

    task_list = []
    for task in tasks:
        coro = task.get_coro()
        if coro:
            task_list.append(
                {
                    "id": id(task),
                    "name": task.get_name(),
                    "state": task._state,
                    "created_at": getattr(task, "created_at", None),
                    "coro": getattr(coro, "__qualname__", str(coro)),
                    "repr": repr(task),
                    "metadata": getattr(task, "metadata", {}),
                }
            )
    response = {"tasks": task_list}
    return resp.success(data=response, uuid=trace_id)
