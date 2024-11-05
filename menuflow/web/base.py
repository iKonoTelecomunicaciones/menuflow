from __future__ import annotations

from aiohttp import web

from ..config import Config
from ..flow_utils import FlowUtils
from ..utils import Util
from ..version import version

_config: Config | None = None
_util: Util | None = None
_flow_utils: FlowUtils | None = None

routes: web.RouteTableDef = web.RouteTableDef()


def set_config(config: Config, flow_utils: FlowUtils) -> None:
    global _config
    global _util
    global _flow_utils

    _util = Util(config=config)
    _config = config
    _flow_utils = flow_utils


def get_config() -> Config:
    return _config


def get_util() -> Util:
    return _util


def get_flow_utils() -> FlowUtils:
    return _flow_utils


@routes.get("/version")
async def get_version(_: web.Request) -> web.Response:
    return web.json_response({"version": version})
