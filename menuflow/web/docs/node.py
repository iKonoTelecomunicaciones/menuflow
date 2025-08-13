from logging import Logger, getLogger

log: Logger = getLogger("ivrflow.docs.node")


get_node_doc = """
    ---
    summary: Search for a node.
    description: Search for a node.
    tags:
        - Node
    parameters:
        - name: flow_id
          in: path
          required: true
          description: The ID of the flow to get the node.
          schema:
            type: integer
        - name: id
          in: path
          required: true
          description: The ID of the node to get.
          schema:
            type: string
          description: Fields to return the list of nodes, if not provided, all fields will be returned.
        - in: query
          name: add_module_name
          schema:
            type: boolean
            default: true
          description: If true, the name of the module associated with the node will be added to the response.
    responses:
        '200':
            $ref: '#/components/responses/GetNodeSuccess'
        '400':
            $ref: '#/components/responses/GetNodeBadRequest'
        '404':
            $ref: '#/components/responses/GetNodeNotFound'
        '500':
            $ref: '#/components/responses/InternalServerError'
"""
