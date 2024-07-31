from __future__ import annotations

from aiohttp import web

from ..config import Config
from ..utils import Util

_config: Config | None = None
_util: Util | None = None

routes: web.RouteTableDef = web.RouteTableDef()


def set_config(config: Config) -> None:
    global _config
    global _util

    _util = Util(config=config)
    _config = config


def get_config() -> Config:
    return _config


@routes.get("/version")
async def version(_: web.Request) -> web.Response:
    return web.json_response({"version": "0.3.5"})
