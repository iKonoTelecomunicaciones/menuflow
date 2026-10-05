from logging import Logger, getLogger

log: Logger = getLogger("menuflow.docs.tag")


webhook_event_doc = """
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
