"""
Meta Dynamic Flow API

This module handles Meta Flow API endpoints for dynamic flows.
Provides encryption/decryption and flow execution functionality.
"""

from __future__ import annotations

from json import JSONDecodeError
from logging import Logger, getLogger

from aiohttp import web

from menuflow.meta_flow.meta_flow import MetaFlow

from ...config import Config
from ...utils.encryption import FlowEndpointException, MetaFlowEncryption
from ..base import get_config, routes
from ..docs.meta import handle_meta_flow_doc
from ..responses import resp
from ..util import Util

log: Logger = getLogger("menuflow.api.meta")


@routes.post("/v1/meta")
@Util.docstring(handle_meta_flow_doc)
async def handle_meta_flow_request(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()

    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Meta flow request started")

    config: Config = get_config()

    # Get private key from config (you'll need to add this to your config)
    log.debug(f"({uuid}) -> Retrieving encryption keys from configuration")
    private_key = config["meta.private_key"]
    private_key_passphrase = config["meta.private_key_passphrase"]
    log.debug(f"({uuid}) -> Private key configured: {bool(private_key)}")

    if not private_key:
        log.error(f"({uuid}) -> Private key not configured for Meta flows")
        return resp.bad_request("Private key not configured", uuid)

    try:
        # Get the encrypted request body
        log.debug(f"({uuid}) -> Parsing encrypted request body")
        encrypted_body = await request.json()
        log.debug(
            f"({uuid}) -> Encrypted body parsed successfully, keys: {list(encrypted_body.keys()) if isinstance(encrypted_body, dict) else 'not_dict'}"
        )
    except JSONDecodeError as e:
        log.error(f"({uuid}) -> Failed to parse JSON from request body: {e}")
        return resp.body_not_json(uuid)

    # Decrypt the request
    log.info(f"({uuid}) -> Starting request decryption process")
    try:
        log.debug(f"({uuid}) -> Calling MetaFlowEncryption.decrypt_request")
        decrypted_data = MetaFlowEncryption.decrypt_request(
            body=encrypted_body, private_pem=private_key, passphrase=private_key_passphrase
        )

        decrypted_body = decrypted_data["decrypted_body"]
        aes_key_buffer = decrypted_data["aes_key_buffer"]
        initial_vector_buffer = decrypted_data["initial_vector_buffer"]

        log.debug(f"({uuid}) -> Successfully decrypted Meta request")
        log.debug(
            f"({uuid}) -> Decrypted body type: {type(decrypted_body)}, keys: {list(decrypted_body.keys()) if isinstance(decrypted_body, dict) else 'not_dict'}"
        )
    except FlowEndpointException as e:
        log.error(f"({uuid}) -> Encryption error: {e.message}")
        return web.Response(status=e.status_code, text=e.message)
    except Exception as e:
        log.error(f"({uuid}) -> Unexpected decryption error: {e}")
        return web.Response(status=500, text="Decryption failed")

    if not isinstance(decrypted_body, dict):
        log.error(f"({uuid}) -> Decrypted body is not a dictionary, type: {type(decrypted_body)}")
        return web.Response(status=400, text="Decrypted body is not a valid JSON object")

    log.debug(f"({uuid}) -> Checking for ping action")
    if decrypted_body.get("action") == "ping":
        log.info(f"({uuid}) -> Received ping action, responding with active status")
        log.debug(f"({uuid}) -> Encrypting ping response")
        encrypted_response = MetaFlowEncryption.encrypt_response(
            {"data": {"status": "active"}}, aes_key_buffer, initial_vector_buffer
        )
        log.debug(f"({uuid}) -> Ping response encrypted successfully")
        return web.Response(text=encrypted_response, content_type="text/plain")

    # Extract room_id and user_id from decrypted body
    data = decrypted_body.get("data", {})
    room_id = data.get("room_id")
    user_id = data.get("mxid")

    if not room_id:
        log.error(f"({uuid}) -> Missing room_id in request body")
        log.debug(f"({uuid}) -> Available data keys: {list(data.keys())}")
        encrypted_error = MetaFlowEncryption.encrypt_response(
            {"error": "Missing room_id in request"}, aes_key_buffer, initial_vector_buffer
        )
        return web.Response(text=encrypted_error, status=400)

    if not user_id:
        log.error(f"({uuid}) -> Missing user_id (mxid) in request body")
        log.debug(f"({uuid}) -> Available data keys: {list(data.keys())}")
        encrypted_error = MetaFlowEncryption.encrypt_response(
            {"error": "Missing user_id in request"}, aes_key_buffer, initial_vector_buffer
        )
        return web.Response(text=encrypted_error, status=400)

    # Execute the meta flow
    log.info(f"({uuid}) -> Initializing MetaFlow execution for user {user_id} in room {room_id}")
    try:
        log.debug(f"({uuid}) -> Creating MetaFlow instance")
        meta_flow = MetaFlow(room_id=room_id, user_id=user_id, uuid=uuid, config=config)

        log.debug(f"({uuid}) -> Starting flow execution with decrypted body")
        response_data = await meta_flow.execute_flow(decrypted_body)

        log.debug(f"({uuid}) -> Flow execution completed successfully")
    except Exception as e:
        log.error(
            f"({uuid}) -> Error executing meta flow for user {user_id} in room {room_id}: {e}"
        )
        encrypted_error = MetaFlowEncryption.encrypt_response(
            {"error": f"Error executing flow: {str(e)}"}, aes_key_buffer, initial_vector_buffer
        )
        return web.Response(text=encrypted_error, status=500)

    # Encrypt and return response
    log.info(f"({uuid}) -> Starting response encryption process")
    try:
        log.debug(f"({uuid}) -> Calling MetaFlowEncryption.encrypt_response")
        encrypted_response = MetaFlowEncryption.encrypt_response(
            response_data, aes_key_buffer, initial_vector_buffer
        )
        log.debug(f"({uuid}) -> Response encrypted successfully")

        log.info(
            f"({uuid}) -> Successfully processed Meta flow request for user {user_id} in room {room_id}"
        )
        return web.Response(text=encrypted_response, content_type="text/plain")

    except Exception as e:
        log.error(
            f"({uuid}) -> Error encrypting response for user {user_id} in room {room_id}: {e}"
        )
        return resp.server_error("Error encrypting response", uuid)
