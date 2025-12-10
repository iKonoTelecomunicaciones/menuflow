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
        - in: query
          name: search
          schema:
            type: string
          description: Search term to filter tags by name.
          example: "prod"
        - in: query
          name: offset
          schema:
            type: integer
            default: 0
          description: Number of tags to skip for pagination.
          example: 0
        - in: query
          name: limit
          schema:
            type: integer
            default: 10
          description: Maximum number of tags to return.
          example: 10

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

restore_tag_doc = """
    ---
    summary: Restore a tag.
    description: Restore a tag by creating a new current tag with the modules and flow variables from the selected tag.
    tags:
        - Tag

    parameters:
        - name: flow_id
          in: path
          required: true
          description: The ID of the flow.
          schema:
            type: integer
          example: 123

    requestBody:
        required: true
        content:
            application/json:
                schema:
                    type: object
                    properties:
                        tag_id:
                            type: integer
                            description: The ID of the tag to restore.
                            example: 1

    responses:
        '200':
            $ref: '#/components/responses/RestoreTagSuccess'
        '400':
            $ref: '#/components/responses/RestoreTagBadRequest'
        '404':
            $ref: '#/components/responses/RestoreTagNotFound'
        '500':
            $ref: '#/components/responses/InternalServerError'
"""

publish_tag_doc = """
    ---
    summary: Publish a tag.
    description: Publish a tag by deactivating the current active tag and activating the selected tag.
    tags:
        - Tag

    parameters:
        - name: flow_id
          in: path
          required: true
          description: The ID of the flow.
          schema:
            type: integer
          example: 123
        - name: tag_id
          in: path
          required: true
          description: The ID of the tag to publish.
          schema:
            type: integer
          example: 1

    responses:
        '200':
            $ref: '#/components/responses/PublishTagSuccess'
        '400':
            $ref: '#/components/responses/PublishTagBadRequest'
        '404':
            $ref: '#/components/responses/PublishTagNotFound'
        '500':
            $ref: '#/components/responses/InternalServerError'
"""
