from __future__ import annotations

from aiohttp import web

from ..config import Config

routes: web.RouteTableDef = web.RouteTableDef()


class Base:
    _config: Config

    @classmethod
    def init_cls(cls, config: Config) -> None:
        cls._config = config

    @classmethod
    def get_config(cls) -> Config:
        return cls._config


@routes.get("/version")
async def version(_: web.Request) -> web.Response:
    return web.json_response({"version": "0.0.1"})
