from __future__ import annotations

import traceback
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
from ...utils.util import Util as Utils
from ..base import get_config, get_flow_utils, routes
from ..responses import resp
from ..util import Util as UtilWeb

log: Logger = getLogger("menuflow.api.misc")


@routes.get("/v1/mis/email_servers", allow_head=False)
async def get_id_email_servers(request: web.Request) -> web.Response:
    """
    ---
    summary: Get email servers registered in flow utils.
    tags:
        - Mis

    responses:
        '200':
            $ref: '#/components/responses/GetEmailServersSuccess'
    """

    name_email_servers = list(FlowUtils.email_servers_by_id.keys())
    return resp.ok({"email_servers": name_email_servers})


@routes.get("/v1/mis/middlewares", allow_head=False)
async def get_id_middlewares(request: web.Request) -> web.Response:
    """
    ---
    summary: Get email servers registered in flow utils.
    tags:
        - Mis

    responses:
        '200':
            $ref: '#/components/responses/GetMiddlewaresSuccess'
    """

    flow_utils = get_flow_utils()
    middlewares = [
        {"id": middleware.id, "type": middleware.type}
        for middleware in flow_utils.data.middlewares
    ]
    return resp.ok({"middlewares": middlewares})


@routes.post("/v1/mis/check_template")
async def check_jinja_template(request: web.Request) -> web.Response:
    """
    ---
    summary: Check jinja syntax
    description: Check if the provided jinja template is valid
    tags:
        - Mis
    requestBody:
        required: true
        content:
            application/x-www-form-urlencoded:
                schema:
                    type: object
                    properties:
                        template:
                            type: string
                            description: The jinja template to be checked
                            example: "Hello {{ name }}"
                        variables:
                            type: string
                            description: >
                                The variables to be used in the template, in `yaml` or `json` format
                            example: "{'name': 'world'}"
                    required:
                        - template
    responses:
        '200':
            $ref: '#/components/responses/CheckTemplateSuccess'
        '400':
            $ref: '#/components/responses/CheckTemplateBadRequest'
        '422':
            $ref: '#/components/responses/CheckTemplateUnprocessable'
    """

    trace_id = UtilWeb.generate_uuid()
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

    return resp.ok({"detail": {"message": "Data rendered", "data": rendered_data}}, trace_id)


@routes.post("/v1/mis/render_data")
async def render_data(request: web.Request) -> web.Response:
    """
    ---
    summary: Check if the result of the rendered template is the same in the actual render data
        and the old one
    description: Check if the provided jinja template is equal to the actual rendered data and
        the old one
    tags:
        - Mis
    requestBody:
        required: true
        content:
            application/x-www-form-urlencoded:
                schema:
                    type: object
                    properties:
                        template:
                            type: string
                            description: The jinja template to be checked
                            example: "Hello {{ name }}"
                        variables:
                            type: string
                            description: >
                                The variables to be used in the template, in `yaml` or `json` format
                            example: "{'name': 'world'}"
                        room_id:
                            type: string
                            description: The ID of the room that will be used in the template to obtain its variables.
                            example: "!room:example.com"
                        old_render:
                            type: boolean
                            description: If true, the old render data will be added to the response
                            example: true
                        string_format:
                            type: boolean
                            description: If true, the new render data will be returned as a string
                            example: true
                    required:
                        - template
    responses:
        '200':
            $ref: '#/components/responses/RenderDataSuccess'
        '400':
            $ref: '#/components/responses/CheckTemplateBadRequest'
        '404':
            $ref: '#/components/responses/RoomIDNotFound'
        '422':
            $ref: '#/components/responses/CheckTemplateUnprocessable'
    """

    trace_id = UtilWeb.generate_uuid()

    try:
        data = await request.post()
    except Exception as e:
        return resp.bad_request(f"Error reading data: {e}", trace_id)

    template = data.get("template")
    variables = data.get("variables")
    room_id = data.get("room_id")
    old_render = Utils.convert_to_type(data.get("old_render", False))
    string_format = Utils.convert_to_type(data.get("string_format", False))

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
        new_render_data = Utils.render_data(template, dict_variables, return_errors=True)
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

    return resp.ok(response, trace_id)


@routes.get("/v1/mis/countries", allow_head=False)
async def countries(request: web.Request) -> web.Response:
    """
    ---
    summary: Return a list with a dictionary of countries with their respective code, languages
        and categories
    description: Return a list with a dictionary of countries
    tags:
        - Mis

    parameters:
        - in: query
          name: language
          description: The language to get the countries in
          required: false
          schema:
            type: string

    responses:
        '200':
            $ref: '#/components/responses/GetCountriesSuccess'
        '500':
            $ref: '#/components/responses/GetCountriesError'
    """
    config: Config = get_config()
    language = request.query.get("language", "es")

    try:
        countries = await Utils(config=config).get_countries(language)
    except GettingDataError as e:
        return resp.server_error(f"Error getting countries: {e}")

    return resp.ok(countries)
