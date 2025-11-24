handle_meta_flow_doc = """
    ---
    summary: Handle Meta flow request.
    tags:
        - Meta

    requestBody:
        required: true
        description: Meta flow encrypted request payload containing encrypted_aes_key, encrypted_flow_data, and initial_vector.
        content:
            application/json:
                schema:
                    type: object
                    required:
                        - encrypted_aes_key
                        - encrypted_flow_data
                        - initial_vector
                    properties:
                        encrypted_aes_key:
                            type: string
                            description: Base64 encoded encrypted AES key
                        encrypted_flow_data:
                            type: string
                            description: Base64 encoded encrypted flow data
                        initial_vector:
                            type: string
                            description: Base64 encoded initial vector
                    example:
                        encrypted_aes_key: "aBc123..."
                        encrypted_flow_data: "dEf456..."
                        initial_vector: "gHi789..."

    responses:
        '200':
            $ref: '#/components/responses/HandleMetaFlowRequestSuccess'
        '400':
            $ref: '#/components/responses/HandleMetaFlowRequestBadRequest'
        '404':
            $ref: '#/components/responses/HandleMetaFlowRequestNotFound'
        '421':
            $ref: '#/components/responses/HandleMetaFlowRequestDecryptionError'
        '500':
            $ref: '#/components/responses/HandleMetaFlowRequestServerError'
"""
