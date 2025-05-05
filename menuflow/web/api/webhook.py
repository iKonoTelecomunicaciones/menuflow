from __future__ import annotations

import asyncio
from logging import Logger, getLogger

from aiohttp import web

from ..base import routes
from ..responses import resp
from ...webhook import Webhook

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
    log.critical("Webhook event received")
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

    webhook_task = asyncio.create_task(Webhook.handle_webhook_event(webhook_event))

    try:
        results = await asyncio.gather(webhook_task, return_exceptions=True)
        log.critical(f"Resultados: {results}")
    except Exception as e:
        log.critical("Error:", e)

    return resp.ok(
        data={"detail": {"message": "Webhook event received", "data": data}},
    )
