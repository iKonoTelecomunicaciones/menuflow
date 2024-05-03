from __future__ import annotations

from http import HTTPStatus
from typing import Optional

from aiohttp import web


class _Response:
    @property
    def body_not_json(self) -> web.Response:
        return web.json_response(
            {
                "error": "Request body is not JSON",
                "errcode": "body_not_json",
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    @property
    def bad_client_access_token(self) -> web.Response:
        return web.json_response(
            {
                "error": "Invalid access token",
                "errcode": "bad_client_access_token",
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    @property
    def bad_client_access_details(self) -> web.Response:
        return web.json_response(
            {
                "error": "Invalid homeserver or access token",
                "errcode": "bad_client_access_details",
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    @property
    def bad_client_connection_details(self) -> web.Response:
        return web.json_response(
            {
                "error": "Could not connect to homeserver",
                "errcode": "bad_client_connection_details",
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    def mxid_mismatch(self, found: str) -> web.Response:
        return web.json_response(
            {
                "error": (
                    "The Matrix user ID of the client and the user ID of the access token don't "
                    f"match. Access token is for user {found}"
                ),
                "errcode": "mxid_mismatch",
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    def device_id_mismatch(self, found: str) -> web.Response:
        return web.json_response(
            {
                "error": (
                    "The Matrix device ID of the client and the device ID of the access token "
                    f"don't match. Access token is for device {found}"
                ),
                "errcode": "mxid_mismatch",
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    @property
    def user_exists(self) -> web.Response:
        return web.json_response(
            {
                "error": "There is already a client with the user ID of that token",
                "errcode": "user_exists",
            },
            status=HTTPStatus.CONFLICT,
        )

    def ok(self, data: Optional[str] = {}) -> web.Response:
        return web.json_response(data, status=HTTPStatus.OK)

    @staticmethod
    def created(data: dict) -> web.Response:
        return web.json_response(data, status=HTTPStatus.CREATED)

    def bad_request(self, message: str) -> web.Response:
        return web.json_response(
            {
                "error": message,
                "errcode": "bad_request",
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    def client_not_found(self, user_id: str) -> web.Response:
        return web.json_response(
            {
                "error": f"Client with user ID {user_id} not found",
                "errcode": "client_not_found",
            },
            status=HTTPStatus.NOT_FOUND,
        )


resp = _Response()
