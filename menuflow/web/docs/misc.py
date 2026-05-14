get_email_servers_doc = """
    ---
    summary: Get email servers registered in flow utils.
    tags:
        - Mis

    responses:
        '200':
            $ref: '#/components/responses/GetEmailServersSuccess'
"""

get_middlewares_doc = """
    ---
    summary: Get email servers registered in flow utils.
    tags:
        - Mis

    responses:
        '200':
            $ref: '#/components/responses/GetMiddlewaresSuccess'
"""

check_jinja_template_doc = """
    ---
    summary: Check jinja syntax
    description: Check if the provided jinja template is valid
    tags:
        - Mis
    requestBody:
        required: true
        content:
            application/x-www-form-urlencoded:
                schema:
                    type: object
                    properties:
                        template:
                            type: string
                            description: The jinja template to be checked
                            example: "Hello {{ name }}"
                        variables:
                            type: string
                            description: >
                                The variables to be used in the template, in `yaml` or `json` format
                            example: "{'name': 'world'}"
                    required:
                        - template
    responses:
        '200':
            $ref: '#/components/responses/CheckTemplateSuccess'
        '400':
            $ref: '#/components/responses/CheckTemplateBadRequest'
        '422':
            $ref: '#/components/responses/CheckTemplateUnprocessable'
"""

render_data_doc = """
    ---
    summary: Check if the result of the rendered template is the same in the actual render data
        and the old one
    description: Check if the provided jinja template is equal to the actual rendered data and
        the old one
    tags:
        - Mis
    requestBody:
        required: true
        content:
            application/x-www-form-urlencoded:
                schema:
                    type: object
                    properties:
                        template:
                            type: string
                            description: The jinja template to be checked
                            example: "Hello {{ name }}"
                        variables:
                            type: string
                            description: >
                                The variables to be used in the template, in `yaml` or `json` format
                            example: "{'name': 'world'}"
                        room_id:
                            type: string
                            description: The ID of the room that will be used in the template to obtain its variables.
                            example: "!room:example.com"
                        old_render:
                            type: boolean
                            description: If true, the old render data will be added to the response
                            example: true
                        string_format:
                            type: boolean
                            description: If true, the new render data will be returned as a string
                            example: true
                    required:
                        - template
    responses:
        '200':
            $ref: '#/components/responses/RenderDataSuccess'
        '400':
            $ref: '#/components/responses/CheckTemplateBadRequest'
        '404':
            $ref: '#/components/responses/RoomIDNotFound'
        '422':
            $ref: '#/components/responses/CheckTemplateUnprocessable'
"""

get_countries_doc = """
    ---
    summary: Return a list with a dictionary of countries with their respective code, languages
        and categories
    description: Return a list with a dictionary of countries
    tags:
        - Mis

    parameters:
        - in: query
          name: language
          description: The language to get the countries in
          required: false
          schema:
            type: string

    responses:
        '200':
            $ref: '#/components/responses/GetCountriesSuccess'
        '500':
            $ref: '#/components/responses/GetCountriesError'
"""

get_task_doc = """
    ---
    summary: Get tasks
    description: Get tasks running in the server. If a name is provided, tasks containing that name will be returned.
    tags:
        - Mis
    parameters:
        - in: query
          name: name
          description: The name of the task to get
          schema:
            type: string
          required: false
    responses:
        '404':
            $ref: '#/components/responses/GetTaskNotFound'
        '200':
            $ref: '#/components/responses/GetTaskSuccess'
"""
