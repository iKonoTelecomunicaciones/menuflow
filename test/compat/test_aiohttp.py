"""Compatibility contracts for aiohttp, aiohttp-cors and aiohttp-swagger3."""

from __future__ import annotations

from types import SimpleNamespace

import aiohttp_cors
import pytest
import pytest_asyncio
from aiohttp import (
    BasicAuth,
    ClientSession,
    ClientTimeout,
    ContentTypeError,
    FormData,
    TraceConfig,
    TraceRequestEndParams,
    TraceRequestStartParams,
    web,
)
from aiohttp.test_utils import TestClient, TestServer
from aiohttp_swagger3 import SwaggerDocs, SwaggerInfo, SwaggerUiSettings


@pytest_asyncio.fixture
async def echo_app():
    app = web.Application()

    async def echo(request: web.Request) -> web.Response:
        auth = request.headers.get("Authorization", "")
        body = await request.read()
        content_type = request.headers.get("Content-Type", "")
        return web.json_response(
            {
                "auth": auth,
                "body": body.decode("utf-8", errors="replace"),
                "content_type": content_type,
                "method": request.method,
            }
        )

    async def plain(request: web.Request) -> web.Response:
        return web.Response(text="not-json", content_type="text/plain")

    app.router.add_route("*", "/echo", echo)
    app.router.add_get("/plain", plain)
    return app


@pytest.mark.asyncio
async def test_client_request_timeout_and_basic_auth(echo_app):
    async with TestServer(echo_app) as server:
        async with ClientSession() as session:
            url = f"http://{server.host}:{server.port}/echo"
            response = await session.request(
                "GET",
                url,
                timeout=ClientTimeout(total=5),
                auth=BasicAuth("user", "pass"),
            )
            data = await response.json()
            assert response.status == 200
            assert data["auth"].startswith("Basic ")


@pytest.mark.asyncio
async def test_content_type_error_on_non_json(echo_app):
    async with TestServer(echo_app) as server:
        async with ClientSession() as session:
            url = f"http://{server.host}:{server.port}/plain"
            response = await session.get(url)
            with pytest.raises(ContentTypeError):
                await response.json()
            text = await response.text()
            assert text == "not-json"


@pytest.mark.asyncio
async def test_form_data_upload(echo_app):
    async with TestServer(echo_app) as server:
        async with ClientSession() as session:
            form = FormData()
            form.add_field("file", b"abc", filename="a.txt", content_type="text/plain")
            form.add_field("purpose", "user_data")
            url = f"http://{server.host}:{server.port}/echo"
            response = await session.post(url, data=form, timeout=ClientTimeout(total=5))
            data = await response.json()
            assert response.status == 200
            assert "multipart" in data["content_type"]
            assert "user_data" in data["body"]


@pytest.mark.asyncio
async def test_trace_config_params_expose_url_and_headers(echo_app):
    seen: dict[str, object] = {}

    async def on_start(session, ctx, params: TraceRequestStartParams):
        seen["start_url"] = str(params.url)
        seen["start_headers"] = params.headers
        assert hasattr(params, "method")

    async def on_end(session, ctx, params: TraceRequestEndParams):
        seen["end_url"] = str(params.url)
        seen["end_headers"] = params.headers
        assert hasattr(params, "response")

    trace = TraceConfig()
    trace.on_request_start.append(on_start)
    trace.on_request_end.append(on_end)

    async with TestServer(echo_app) as server:
        async with ClientSession(trace_configs=[trace]) as session:
            url = f"http://{server.host}:{server.port}/echo"
            response = await session.get(url, trace_request_ctx={"middleware": None})
            assert response.status == 200

    assert "/echo" in seen["start_url"]
    assert seen["start_headers"] is not None
    assert "/echo" in seen["end_url"]
    # Menuflow reads params.url / params.headers from both start and end hooks.
    assert isinstance(seen["start_url"], str)


@pytest.mark.asyncio
async def test_swagger3_and_cors_management_app_boots():
    app = web.Application()

    async def ping(_: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    swagger = SwaggerDocs(
        app,
        info=SwaggerInfo(title="Menuflow Compat", description="compat", version="test"),
        components="menuflow/web/api/components.yaml",
        swagger_ui_settings=SwaggerUiSettings(path="/docs", layout="BaseLayout"),
    )
    swagger.add_routes([web.get("/v1/ping", ping)])

    cors = aiohttp_cors.setup(
        app,
        defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods=["GET", "POST", "OPTIONS", "PATCH", "DELETE"],
            )
        },
    )
    for route in list(app.router.routes()):
        cors.add(route)

    async with TestClient(TestServer(app)) as client:
        response = await client.get("/v1/ping")
        assert response.status == 200
        assert await response.json() == {"ok": True}
        docs = await client.get("/docs")
        assert docs.status == 200


def test_trace_param_types_importable():
    assert TraceRequestStartParams is not None
    assert TraceRequestEndParams is not None
    assert SimpleNamespace is not None
