from __future__ import annotations

from logging import Logger, getLogger

from aiohttp import web

from ...webhook.webhook_handler import WebhookHandler
from ..base import routes
from ..docs.webhook import webhook_event_doc
from ..responses import resp
from ..util import Util

log: Logger = getLogger("menuflow.api.webhook")


@routes.post("/v1/webhook/event")
@Util.docstring(webhook_event_doc)
async def handle_request(request: web.Request) -> web.Response:
    trace_id = Util.generate_uuid()
    log.info(f"({trace_id}) -> '{request.method}' '{request.path}' Webhook event received")
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

    status, message = await WebhookHandler(trace_id=trace_id).handle_webhook_event(webhook_event)

    return resp.management_response(message=message, data=data, status=status, uuid=trace_id)
