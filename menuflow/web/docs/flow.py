from logging import Logger, getLogger

log: Logger = getLogger("ivrflow.docs.flow")

create_or_update_flow_doc = """
    ---
    summary: Creates a new flow or update it if exists.
    tags:
        - Flow

    requestBody:
        required: false
        description: A json with `id` and `flow` keys.
                     `id` is the flow ID to update, `flow` is the flow content.
        content:
            application/json:
                schema:
                    type: object
                    properties:
                        id:
                            type: integer
                        flow:
                            type: object
                    required:
                        - flow
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
