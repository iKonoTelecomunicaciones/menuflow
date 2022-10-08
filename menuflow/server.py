from __future__ import annotations

import asyncio
import logging

from aiohttp import web
from aiohttp.abc import AbstractAccessLogger

from .config import Config


class AccessLogger(AbstractAccessLogger):
    def log(self, request: web.Request, response: web.Response, time: int):
        self.logger.info(
            f'{request.remote} "{request.method} {request.path} '
            f"{response.status} {response.body_length} "
            f'in {round(time, 4)}s"'
        )


class MenuFlowServer:
    log: logging.Logger = logging.getLogger("menuflow.server")

    def __init__(
        self, management_api: web.Application, config: Config, loop: asyncio.AbstractEventLoop
    ) -> None:
        self.loop = loop or asyncio.get_event_loop()
        self.app = web.Application(loop=self.loop, client_max_size=100 * 1024 * 1024)
        self.config = config

        self.app.add_subapp(config["server.base_path"], management_api)
        self.runner = web.AppRunner(self.app, access_log_class=AccessLogger)

    async def start(self) -> None:
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.config["server.hostname"], self.config["server.port"])
        await site.start()
        self.log.info(f"Listening on {site.name}")

    async def stop(self) -> None:
        await self.runner.shutdown()
        await self.runner.cleanup()
