from __future__ import annotations

from aiohttp import web

from ...flow_utils import FlowUtils
from ..base import routes
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

    name_email_servers = [name for name in FlowUtils.email_servers_by_id.keys()]
    return resp.ok({"email_servers": name_email_servers})
