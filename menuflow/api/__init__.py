from asyncio import AbstractEventLoop

import aiohttp_cors
from aiohttp import web

from ..config import Config
from .base import Base, routes

all_endpoints = ["client"]


def init(cfg: Config, loop: AbstractEventLoop) -> web.Application:
    Base.init_cls(cfg)
    app = web.Application(loop=loop, client_max_size=100 * 1024 * 1024)
    app.add_routes(routes)
    cors = aiohttp_cors.setup(
        app,
        defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods=["GET", "POST", "OPTIONS", "PATCH", "PUT"],
            )
        },
    )

    for route in list(app.router.routes()):
        cors.add(route)

    return app
