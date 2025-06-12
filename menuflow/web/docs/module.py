from logging import Logger, getLogger
from textwrap import indent

log: Logger = getLogger("menuflow.docs.module")


def template_indent(template: str, indent_level: int = None) -> str:
    """
    Get the example with the given indent level.

    Parameters
    ----------
    template: str
        The template to get the indent level from.
    indent_level: int
        The indent level to get the template with.

    Returns
    -------
    str
        The example with the given indent level.
    """
    lines = template.strip().splitlines()
    return lines[0] + "\n" + indent("\n".join(lines[1:]), " " * (indent_level or 20))


template_nodes = """
nodes:
    - x: 501.04994916101714
      y: -627.2362469450213
      id: "message_hello"
      name: "message_hello"
      text: "Hello, world! 😀"
      type: "message"
      message_type: "m.text"
"""

template_position = """
position:
    x: 632.8705383300783
    y: 357.11742401123036
    scale: 0.4092324994498387
"""

template_body_create = f"""
name: "example"
{template_indent(template_nodes)}
{template_indent(template_position)}
"""

get_module_doc = """
    ---
    summary: Get module by ID or client MXID.
    tags:
        - Module

    parameters:
        - in: path
          name: flow_id
          schema:
            type: integer
          required: true
          description: The flow ID to get the modules.
        - in: query
          name: id
          schema:
            type: integer
          description: The module ID to get.
        - in: query
          name: name
          schema:
            type: string
          description: The module name to get.

    responses:
        '200':
            $ref: '#/components/responses/GetModuleSuccess'
        '404':
            $ref: '#/components/responses/GetModuleNotFound'
"""

create_module_doc = f"""
    ---
    summary: Create a new module.
    tags:
        - Module

    parameters:
        - name: flow_id
          in: path
          required: true
          description: The ID of the flow to update the module.
          schema:
            type: integer

    requestBody:
        required: true
        content:
            application/json:
                schema:
                    type: object
                    properties:
                        name:
                            type: string
                            description: The name of the module.
                        nodes:
                            type: array
                            items:
                                type: object
                        position:
                            type: object
                    required:
                        - name
                        - nodes
                        - position
                example:
                    {template_indent(template_body_create, 20)}
    responses:
        '200':
            $ref: '#/components/responses/UpdateModuleSuccess'
        '400':
            $ref: '#/components/responses/UpdateModuleBadRequest'
  """

update_module_doc = f"""
    ---
    summary: Update an existing module.
    description: Update the properties of an existing module.

    tags:
        - Module

    parameters:
        - name: module_id
          in: path
          required: true
          description: The ID of the module to update.
          schema:
            type: integer
          example: 1
        - name: flow_id
          in: path
          required: true
          description: The ID of the flow to update the module.
          schema:
            type: integer

    requestBody:
        required: true
        content:
            application/json:
                schema:
                    type: object
                    properties:
                        name:
                            type: string
                        nodes:
                            type: array
                            items:
                                type: object
                        position:
                            type: object
                examples:
                    UpdateName:
                        value:
                            name: "example"
                    UpdateNodes:
                        value:
                            {template_indent(template_nodes, 28)}
                    UpdatePosition:
                        value:
                            {template_indent(template_position, 28)}
                    UpdateAll:
                        value:
                            {template_indent(template_body_create, 28)}

    responses:
        '200':
            $ref: '#/components/responses/CreateModuleSuccess'
        '400':
            $ref: '#/components/responses/CreateModuleBadRequest'
        '404':
            $ref: '#/components/responses/UpdateModuleNotFound'
  """

delete_module_doc = """
    ---
    summary: Delete an existing module.
    description: Delete an existing module.

    tags:
        - Module

    parameters:
        - name: module_id
          in: path
          required: true
          description: The ID of the module to delete.
          schema:
            type: integer
          example: 1
        - name: flow_id
          in: path
          required: true
          description: The ID of the flow to delete the module.
          schema:
            type: integer

    responses:
        '200':
            $ref: '#/components/responses/DeleteModuleSuccess'
        '404':
            $ref: '#/components/responses/DeleteModuleNotFound'
  """
