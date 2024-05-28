from __future__ import annotations

from http import HTTPStatus
from typing import Dict, Optional

from aiohttp import web


class _Response:
    @property
    def body_not_json(self) -> web.Response:
        return web.json_response(
            {"detail": {"message": "Request body is not JSON"}},
            status=HTTPStatus.BAD_REQUEST,
        )

    @property
    def bad_client_access_token(self) -> web.Response:
        return web.json_response(
            {"detail": {"message": "Invalid access token"}},
            status=HTTPStatus.BAD_REQUEST,
        )

    @property
    def bad_client_access_details(self) -> web.Response:
        return web.json_response(
            {"detail": {"message": "Invalid homeserver or access token"}},
            status=HTTPStatus.BAD_REQUEST,
        )

    @property
    def bad_client_connection_details(self) -> web.Response:
        return web.json_response(
            {"detail": {"message": "Could not connect to homeserver"}},
            status=HTTPStatus.BAD_REQUEST,
        )

    def mxid_mismatch(self, found: str) -> web.Response:
        return web.json_response(
            {
                "detail": {
                    "message": f"""
                        The Matrix user ID of the client and the user ID of the access token don't
                        match. Access token is for user {found}
                    """
                }
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    def device_id_mismatch(self, found: str) -> web.Response:
        return web.json_response(
            {
                "detail": {
                    "message": """
                        The Matrix device ID of the client and the device ID of the access token
                        don't match. Access token is for device {found}
                    """
                },
                "errcode": "mxid_mismatch",
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    @property
    def user_exists(self) -> web.Response:
        return web.json_response(
            {"detail": {"message": "There is already a client with the user ID of that token"}},
            status=HTTPStatus.CONFLICT,
        )

    def ok(self, data: Optional[Dict] = {}) -> web.Response:
        return web.json_response(data, status=HTTPStatus.OK)

    @staticmethod
    def created(data: dict) -> web.Response:
        return web.json_response(data, status=HTTPStatus.CREATED)

    def bad_request(self, message: str) -> web.Response:
        return web.json_response(
            {"detail": {"message": message}},
            status=HTTPStatus.BAD_REQUEST,
        )

    def client_not_found(self, user_id: str) -> web.Response:
        return web.json_response(
            {"detail": {"message": f"Client with user ID {user_id} not found"}},
            status=HTTPStatus.NOT_FOUND,
        )

    def not_found(self, message: str) -> web.Response:
        return web.json_response(
            {
                "detail": {"message": message},
            },
            status=HTTPStatus.NOT_FOUND,
        )


resp = _Response()
