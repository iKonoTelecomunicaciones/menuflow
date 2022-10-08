from __future__ import annotations

from aiohttp import web

from ..config import Config

routes: web.RouteTableDef = web.RouteTableDef()
_config: Config | None = None


def set_config(config: Config) -> None:
    global _config
    _config = config


def get_config() -> Config:
    return _config


@routes.get("/version")
async def version(_: web.Request) -> web.Response:

    return web.json_response({"version": "0.0.1"})
