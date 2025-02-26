from __future__ import annotations

import traceback
from logging import Logger, getLogger

import yaml
from aiohttp import web
from jinja2.exceptions import TemplateSyntaxError, UndefinedError

from ...flow_utils import FlowUtils
from ...jinja.jinja_template import jinja_env
from ..base import get_flow_utils, routes
from ..responses import resp
from ..util import Util

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

    trace_id = Util.generate_uuid()

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
        temp_rendered = template.render(**dict_variables) if variables else template.render()
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

    return resp.ok({"rendered": temp_rendered}, trace_id)
