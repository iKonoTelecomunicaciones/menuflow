from asyncio import AbstractEventLoop

from aiohttp import web

import menuflow

from ..config import Config
from .base import routes, set_config

all_endpoints = ["client"]


def init(cfg: Config, loop: AbstractEventLoop) -> web.Application:
    set_config(cfg)
    app = web.Application(loop=loop, client_max_size=100 * 1024 * 1024)
    app.add_routes(routes)
    return app
