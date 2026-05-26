simulate_event_doc = """
    ---
    summary: Simulate a Matrix event for the bot
    description: |
      Builds a join, leave, or message event and dispatches it to the same handlers used by sync.
      The response returns immediately (202); processing runs asynchronously.

      For replay testing, set `timestamp` (ms) newer than the last join/message stored for the room,
      otherwise handlers may ignore the event.
    tags:
        - Client

    parameters:
        - name: mxid
          in: path
          required: true
          description: Matrix user ID of the bot client
          schema:
            type: string
          example: "@bot:example.com"

    requestBody:
        required: true
        content:
            application/json:
                schema:
                    type: object
                    properties:
                        event_type:
                            type: string
                            enum: [join, leave, message]
                        room_id:
                            type: string
                        sender:
                            type: string
                            description: >
                              Required for message (must not be the bot). Optional for join/leave
                              (defaults to the bot mxid).
                        body:
                            type: string
                            description: Message text (required if event_type is message)
                        msgtype:
                            type: string
                            default: m.text
                        timestamp:
                            type: integer
                            description: Event time in milliseconds since epoch (optional)
                        event_id:
                            type: string
                            description: Custom event id (optional; default is $sim-...)
                    required:
                        - event_type
                        - room_id
                example:
                    event_type: message
                    room_id: "!vOmHZZMQibXsynuNFm:example.com"
                    sender: "@user:example.com"
                    body: "Hello"
                    msgtype: m.text
                    timestamp: 1710000000000

    responses:
        '202':
            description: Event accepted and queued for handling
            content:
                application/json:
                    schema:
                        type: object
                        properties:
                            detail:
                                type: object
        '400':
            $ref: '#/components/responses/CreateClientBadRequest'
        '404':
            $ref: '#/components/responses/ClientEnableOrDisableNotFound'
        '422':
            description: The event payload could not be parsed into a Matrix event
            content:
                application/json:
                    schema:
                        $ref: '#/components/schemas/BaseResponseDetailMessage'
"""
