from logging import Logger, getLogger

log: Logger = getLogger("menuflow.docs.client")


create_client_doc = """
    ---
    summary: Create a new client
    description: Create a new client with the provided homeserver and access token
    tags:
        - Client

    requestBody:
        required: false
        content:
            application/json:
                schema:
                    type: object
                    properties:
                        homeserver:
                            type: string
                        access_token:
                            type: string
                        device_id:
                            type: string
                        enabled:
                            type: boolean
                        autojoin:
                            type: boolean
                    required:
                        - homeserver
                        - access_token
                example:
                    homeserver: "https://matrix.org"
                    access_token: "sk_MDAxOGxvY2F0aW9uIG1hdXRyaXgub3JnCjAwMTBja"
                    device_id: "DFKEN36"
                    enabled: true
                    autojoin: true
    responses:
        '201':
            $ref: '#/components/responses/CreateClientSuccess'
        '400':
            $ref: '#/components/responses/CreateClientBadRequest'
"""

set_variables_doc = """
    ---
    summary: Set variables
    description: Set variables for a room
    tags:
        - Room

    parameters:
        - name: room_id
          in: path
          required: true
          description: The room ID to set variables for
          schema:
            type: string
          example: "!vOmHZZMQibXsynuNFm:example.com"

    requestBody:
        required: true
        content:
            application/json:
                schema:
                    type: object
                    properties:
                        variables:
                            type: object
                        bot_mxid:
                            type: string
                        conversation_uuid:
                            type: string
                example:
                    variables:
                        var1: value
                        var2: value
                    bot_mxid: "@bot:example.com"
                    conversation_uuid: "1234567890"
    responses:
        '201':
            $ref: '#/components/responses/VariablesSetSuccess'
        '500':
            $ref: '#/components/responses/InternalServerError'
"""

reload_client_flow_doc = """
    ---
    summary: Reload a client's flow
    description: Reload the flow of a client

    tags:
        - Client

    parameters:
        - name: mxid
          in: path
          required: true
          description: The Matrix user ID of the client
          schema:
            type: string
          example: "@client:example.com"

    responses:
        '200':
            $ref: '#/components/responses/ClientFlowReloaded'
        '404':
            $ref: '#/components/responses/ClientReloadFlowNotFound'
"""

enable_disable_client_doc = """
    ---
    summary: Enable or disable a client
    description: Enable or disable a client

    tags:
        - Client

    parameters:
        - name: mxid
          in: path
          required: true
          description: The Matrix user ID of the client
          schema:
            type: string
          example: "@client:example.com"

        - name: action
          in: path
          required: true
          description: The action to perform
          schema:
            type: string
          example: "enable | disable"

    responses:
        '200':
            $ref: '#/components/responses/ClientEnabledOrDisabled'
        '400':
            $ref: '#/components/responses/ClientEnableOrDisableBadRequest'
        '404':
            $ref: '#/components/responses/ClientEnableOrDisableNotFound'
"""

get_variables_doc = """
    ---
    summary: Get variables
    description: Get variables
    tags:
        - Room

    parameters:
        - name: room_id
          in: path
          required: true
          description: The room ID to set variables for
          schema:
            type: string
          example: "!vOmHZZMQibXsynuNFm:example.com"

        - name: bot_mxid
          in: query
          description: The Matrix user ID of the client
          schema:
            type: string
          example: "@bot:example.com"

        - name: scopes
          in: query
          required: false
          description: The scopes of the variables to get. If not provided, all variables will be returned.
          schema:
            type: array
            default: ["room", "route", "node", "external"]
            items:
              type: string

        - name: all_custom_scopes
          in: query
          required: false
          description: If true, all custom scopes will be returned.
          schema:
            type: boolean
            default: false

    responses:
        '200':
            $ref: '#/components/responses/GetVariablesSuccess'
        '404':
            $ref: '#/components/responses/GetVariablesNotFound'
        '500':
            $ref: '#/components/responses/InternalServerError'
"""

status_doc = """
    ---
    summary: Get status
    description: Get status
    tags:
        - Room

    parameters:
        - name: room_id
          in: path
          required: true
          description: The room ID to get the status of the client
          schema:
            type: string
          example: "!vOmHZZMQibXsynuNFm:example.com"

        - name: bot_mxid
          in: query
          required: false
          description: The Matrix user ID of the client
          schema:
            type: string
          example: "@bot:example.com"

    responses:
        '200':
            $ref: '#/components/responses/GetStatusSuccess'
        '404':
            $ref: '#/components/responses/GetStatusNotFound'
        '500':
            $ref: '#/components/responses/InternalServerError'
"""

delete_scope_doc = """
    ---
    summary: Delete a custom scope
    description: Delete a custom scope
    tags:
        - Room

    parameters:
        - name: room_id
          in: path
          required: true
          description: The room ID to delete the scope from
          schema:
            type: string
          example: "!vOmHZZMQibXsynuNFm:example.com"

        - name: scope
          in: path
          required: true
          description: The scope to delete
          schema:
            type: string
          example: "custom_scope"

    responses:
        '200':
            $ref: '#/components/responses/DeleteScopeSuccess'
        '400':
            $ref: '#/components/responses/DeleteScopeBadRequest'
        '404':
            $ref: '#/components/responses/DeleteScopeNotFound'
        '500':
            $ref: '#/components/responses/InternalServerError'
"""
