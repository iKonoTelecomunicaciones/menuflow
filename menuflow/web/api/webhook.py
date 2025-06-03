from __future__ import annotations

from logging import Logger, getLogger

from aiohttp import web

from ...webhook.webhook_handler import WebhookHandler
from ..base import routes
from ..responses import resp
from ..util import Util

log: Logger = getLogger("menuflow.api.webhook")


@routes.post("/v1/webhook/event")
async def handle_request(request: web.Request) -> web.Response:
    """
    ---
    summary: Webhook event for management the waiting node
    tags:
        - Webhook

    requestBody:
        required: true
        content:
            application/json:
                schema:
                    type: object
                    additionalProperties: true
                    example:
                        id: 123456789
                        client: John Doe
                        paid: true
            application/x-www-form-urlencoded:
                schema:
                    type: object
                    additionalProperties: true
                    example:
                        id: 123456789
                        client: John Doe
                        paid: true
    responses:
        '200':
            $ref: '#/components/responses/EventSuccess'
        '415':
            $ref: '#/components/responses/UnsupportedContentType'
    """
    trace_id = Util.generate_uuid()
    content_type = request.headers.get("Content-Type", default="")

    if not content_type.startswith("application/json") and not content_type.startswith(
        "application/x-www-form-urlencoded"
    ):
        return resp.unsupported_content_type()

    if content_type.startswith("application/json"):
        data = await request.json()
    else:
        data = await request.post()

    webhook_event = data
    log.info(f"Webhook event received {webhook_event}")

    status, message = await WebhookHandler.handle_webhook_event(webhook_event)

    return resp.management_response(
        message=message,
        data=data,
        status=status,
    )
