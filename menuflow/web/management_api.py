from __future__ import annotations

import asyncio
import logging
from typing import Dict

import aiohttp_cors
from aiohttp import web
from aiohttp_swagger3 import SwaggerDocs, SwaggerInfo, SwaggerUiSettings
from mautrix.util.logging import TraceLogger

from ..config import Config
from . import api
from .base import routes, set_config


class ManagementAPI:
    """Management API base class"""

    log: TraceLogger = logging.getLogger("menuflow.management_api")
    app: web.Application

    def __init__(self, config: Config, loop: asyncio.AbstractEventLoop) -> None:
        self.app = web.Application()
        self.loop = loop
        set_config(config=config)

        swagger = SwaggerDocs(
            self.app,
            info=SwaggerInfo(
                title="Menuflow API",
                description=(
                    "Documentation for Menuflow matrix bot builder "
                    "project by **iKono Telecomunicaciones S.A.S.**"
                ),
                version=f"v0.3.5",
            ),
            components="menuflow/web/api/components.yaml",
            swagger_ui_settings=SwaggerUiSettings(
                path="/docs",
                layout="BaseLayout",
            ),
        )

        swagger.add_routes(routes)

        cors = aiohttp_cors.setup(
            self.app,
            defaults={
                "*": aiohttp_cors.ResourceOptions(
                    allow_credentials=True,
                    expose_headers="*",
                    allow_headers="*",
                    allow_methods=["GET", "POST", "OPTIONS", "PATCH", "DELETE"],
                )
            },
        )

        for route in list(self.app.router.routes()):
            cors.add(route)
            if route.method in ["post", "POST"]:
                route_info: Dict = route.get_info()
                swagger.add_options(
                    path=route_info.get("path") or route_info.get("formatter"),
                    handler=self.options,
                )

    @property
    def _acao_headers(self) -> dict[str, str]:
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS, PATCH, DELETE",
        }

    @property
    def _headers(self) -> dict[str, str]:
        return {
            **self._acao_headers,
            "Content-Type": "application/json",
        }

    async def options(self, _: web.Request):
        return web.Response(status=200, headers=self._headers)
