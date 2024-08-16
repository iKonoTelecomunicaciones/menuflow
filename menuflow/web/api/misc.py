from __future__ import annotations

from aiohttp import web

from ...flow_utils import FlowUtils
from ..base import get_flow_utils, routes
from ..responses import resp


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
