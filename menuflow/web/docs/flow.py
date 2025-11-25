from logging import Logger, getLogger

log: Logger = getLogger("menuflow.docs.flow")

create_or_update_flow_doc = """
    ---
    summary: Creates a new flow or update it if exists.
    deprecated: true
    tags:
        - Flow

    requestBody:
        required: false
        description: A json with `id`, `flow` and `flow_vars` keys.
                     `id` is the flow ID to update, `flow` is the flow content, `flow_vars` is the flow variables.
        content:
            application/json:
                schema:
                    type: object
                    properties:
                        id:
                            type: integer
                        flow:
                            type: object
                        flow_vars:
                            type: object
                            additionalProperties: true
                    example:
                        id: 1
                        flow:
                            menu:
                                flow_variables:
                                    var1: "value1"
                                    var2: "value2"
                                nodes:
                                    - id: 1
                                      type: "message"
                                      content: "Hello"
                                      o_connection: 2
                        flow_vars:
                            var1: "value1"
                            var2: "value2"
    responses:
        '200':
            $ref: '#/components/responses/CreateUpdateFlowSuccess'
        '400':
            $ref: '#/components/responses/CreateUpdateFlowBadRequest'
    """

get_flow_doc = """
    ---
    summary: Get flow by ID or client MXID.
    tags:
        - Flow

    parameters:
        - in: query
          name: id
          schema:
            type: integer
          description: The flow ID to get.
        - in: query
          name: client_mxid
          schema:
            type: string
          description: The client MXID to get the flow.
        - in: query
          name: flow_format
          schema:
            type: boolean
            default: false
          description: Return the old flow format.

    responses:
        '200':
            $ref: '#/components/responses/GetFlowSuccess'
        '404':
            $ref: '#/components/responses/GetFlowNotFound'
    """

get_flow_nodes_doc = """
    ---
    summary: Get flow nodes by ID or client MXID
    tags:
        - Flow

    parameters:
        - in: path
          name: flow_identifier
          schema:
            type: string
          required: true
          description: The flow identifier to obtain can be `id` or `mxid`.
        - in: query
          name: flow_format
          schema:
            type: boolean
            default: false
          description: Return the old flow format.
        - in: query
          name: filters_nodes
          schema:
            type: array
            default: ["id", "type", "name"]
            items:
              type: string
          description: List of nodes to filter.

    responses:
        '200':
            $ref: '#/components/responses/GetFlowNodesSuccess'
        '404':
            $ref: '#/components/responses/GetFlowNotFound'
    """

get_flow_backups_doc = """
    ---
    summary: Get flow backups by flow ID.
    tags:
        - Flow

    parameters:
        - in: path
          name: flow_id
          description: The flow ID to get the backups.
          required: true
          schema:
            type: integer

        - in: query
          name: limit
          description: The limit of backups to get.
          schema:
            type: integer

        - in: query
          name: offset
          description: The offset of backups to get.
          schema:
            type: integer

        - in: query
          name: backup_id
          description: The backup ID to get.
          schema:
              type: integer

    responses:
        '200':
            $ref: '#/components/responses/GetFlowBackupsSuccess'
        '404':
            $ref: '#/components/responses/GetFlowBackupsNotFound'

    """

publish_flow_doc = """
    ---
    summary: Publish a flow by creating a new tag.
    description: Creates a new tag from the current tag, copies all modules, and activates the new tag.
    tags:
        - Flow

    parameters:
        - name: flow_id
          in: path
          required: true
          description: The ID of the flow to publish.
          schema:
            type: integer
          example: 1

    requestBody:
        required: true
        content:
            application/json:
                schema:
                    type: object
                    properties:
                        name:
                            type: string
                            description: The name of the new tag.
                        author:
                            type: string
                            description: The author of the tag.
                    required:
                        - name
                        - author
                example:
                    name: "v1.0.0"
                    author: "@admin:example.com"

    responses:
        '200':
            $ref: '#/components/responses/PublishFlowSuccess'
        '400':
            $ref: '#/components/responses/PublishFlowBadRequest'
        '404':
            $ref: '#/components/responses/PublishFlowNotFound'
        '500':
            $ref: '#/components/responses/PublishFlowInternalError'
    """

import_flow_doc = """
    ---
    summary: Import a flow.
    description: Import a flow by updating an existing flow with new flow data. The flow ID must be provided.
    tags:
        - Flow

    requestBody:
        required: true
        description: A JSON with 'id', 'flow' and 'flow_vars' keys. The 'id' is required for import.
        content:
            application/json:
                schema:
                    type: object
                    properties:
                        id:
                            type: integer
                            description: The flow ID to import (required).
                        flow:
                            type: object
                            description: The flow content.
                        flow_vars:
                            type: object
                            additionalProperties: true
                            description: The flow variables.
                    required:
                        - id
                example:
                    id: 1
                    flow:
                        menu:
                            flow_variables:
                                var1: "value1"
                                var2: "value2"
                            nodes:
                                - id: "message_1"
                                  type: "message"
                                  text: "Hello"
                                  o_connection: "message_2"
                        modules:
                            main:
                                x: 100
                                y: 200
                                scale: 1.0
                    flow_vars:
                        var1: "value1"
                        var2: "value2"

    responses:
        '200':
            $ref: '#/components/responses/ImportFlowSuccess'
        '400':
            $ref: '#/components/responses/ImportFlowBadRequest'
        '404':
            $ref: '#/components/responses/ImportFlowNotFound'
        '500':
            $ref: '#/components/responses/InternalServerError'
    """
