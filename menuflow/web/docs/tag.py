from logging import Logger, getLogger

from ..util import Util

log: Logger = getLogger("menuflow.docs.tag")


template_tag_response = """
id: 1
flow_id: 123
name: "production"
create_date: "2025-11-21 10:00:00"
author: "@user:example.com"
active: true
flow_vars:
    variable1: "value1"
    variable2: "value2"
"""

template_tags_list_response = """
tags:
    - id: 1
      flow_id: 123
      name: "production"
      create_date: "2025-11-21 10:00:00"
      author: "@user:example.com"
      active: true
      flow_vars:
          variable1: "value1"
    - id: 2
      flow_id: 123
      name: "staging"
      create_date: "2025-11-21 09:00:00"
      author: "@user:example.com"
      active: false
      flow_vars:
          variable1: "value2"
"""

get_tags_by_flow_doc = f"""
    ---
    summary: Get tags by flow ID.
    description: Retrieve tags for a specific flow. Can filter by tag ID or tag name, or retrieve all tags for the flow.
    tags:
        - Tag

    parameters:
        - in: path
          name: flow_id
          schema:
            type: integer
          required: true
          description: The flow ID to get the tags from.
          example: 123
        - in: query
          name: id
          schema:
            type: integer
          description: The tag ID to get a specific tag.
          example: 1
        - in: query
          name: name
          schema:
            type: string
          description: The tag name to get a specific tag.
          example: "production"

    responses:
        '200':
            $ref: '#/components/responses/GetTagsSuccess'
        '400':
            $ref: '#/components/responses/GetTagsBadRequest'
        '404':
            $ref: '#/components/responses/GetTagsNotFound'
        '500':
            $ref: '#/components/responses/InternalServerError'
"""

delete_tag_doc = """
    ---
    summary: Delete a tag.
    description: Delete an existing tag. Only inactive tags can be deleted.
    tags:
        - Tag

    parameters:
        - name: tag_id
          in: path
          required: true
          description: The ID of the tag to delete.
          schema:
            type: integer
          example: 1

    responses:
        '200':
            $ref: '#/components/responses/DeleteTagSuccess'
        '400':
            $ref: '#/components/responses/DeleteTagBadRequest'
        '404':
            $ref: '#/components/responses/DeleteTagNotFound'
        '409':
            $ref: '#/components/responses/DeleteTagConflict'
        '500':
            $ref: '#/components/responses/InternalServerError'
"""
