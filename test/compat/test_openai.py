"""Compatibility contracts for the OpenAI SDK surface used by GPTAssistant."""

from __future__ import annotations

import inspect
import json
from typing import Any

import httpx
import openai
import pytest
from pytest_mock import MockerFixture

from menuflow.config import Config
from menuflow.nodes.gpt_assistant import GPTAssistant
from menuflow.room import Room

FILE_OBJECT = {
    "id": "file-abc123",
    "object": "file",
    "bytes": 4,
    "created_at": 1_700_000_000,
    "filename": "a.pdf",
    "purpose": "user_data",
    "status": "processed",
}

RESPONSE_OBJECT = {
    "id": "resp_1",
    "object": "response",
    "created_at": 1_700_000_000,
    "status": "completed",
    "model": "gpt-4o-mini",
    "output": [
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": "hola mundo", "annotations": []}],
        }
    ],
    "error": None,
    "incomplete_details": None,
    "instructions": None,
    "metadata": {},
    "parallel_tool_calls": True,
    "temperature": 1.0,
    "tool_choice": "auto",
    "tools": [],
    "top_p": 1.0,
    "usage": {
        "input_tokens": 1,
        "output_tokens": 1,
        "total_tokens": 2,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens_details": {"reasoning_tokens": 0},
    },
}


def _mock_client(
    handler,
    *,
    max_retries: int = 0,
) -> openai.AsyncOpenAI:
    transport = httpx.MockTransport(handler)
    return openai.AsyncOpenAI(
        api_key="test-key",
        timeout=GPTAssistant.OPENAI_TIMEOUT,
        http_client=httpx.AsyncClient(transport=transport),
        max_retries=max_retries,
    )


def test_async_openai_accepts_api_key_and_timeout():
    sig = inspect.signature(openai.AsyncOpenAI.__init__)
    assert "api_key" in sig.parameters
    assert "timeout" in sig.parameters
    assert "http_client" in sig.parameters


@pytest.mark.asyncio
async def test_files_create_sends_expires_after_and_returns_id():
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.content
        assert request.method == "POST"
        assert request.url.path.endswith("/files")
        return httpx.Response(200, json=FILE_OBJECT)

    client = _mock_client(handler)
    uploaded = await client.files.create(
        file=("a.pdf", b"%PDF", "application/pdf"),
        purpose="user_data",
        expires_after={"anchor": "created_at", "seconds": 3600},
    )

    assert uploaded.id == "file-abc123"
    body = seen["body"]
    assert isinstance(body, (bytes, bytearray))
    assert b'name="purpose"' in body
    assert b"user_data" in body
    assert b"expires_after" in body
    assert b"created_at" in body
    assert b"3600" in body


@pytest.mark.asyncio
async def test_responses_create_payload_and_output_text():
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content.decode())
        assert request.url.path.endswith("/responses")
        return httpx.Response(200, json=RESPONSE_OBJECT)

    client = _mock_client(handler)
    input_messages = [
        {"role": "user", "content": [{"type": "input_text", "text": "hi"}]},
    ]
    response = await client.responses.create(
        model="gpt-4o-mini",
        input=input_messages,
        instructions="be brief",
    )

    assert response.output_text == "hola mundo"
    assert seen["body"]["model"] == "gpt-4o-mini"
    assert seen["body"]["input"] == input_messages
    assert seen["body"]["instructions"] == "be brief"


@pytest.mark.asyncio
async def test_http_error_raises_api_error_subclass():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "message": "bad request",
                    "type": "invalid_request_error",
                    "code": "invalid",
                }
            },
        )

    client = _mock_client(handler)
    with pytest.raises(openai.APIError) as exc_info:
        await client.responses.create(
            model="gpt-4o-mini",
            input=[{"role": "user", "content": [{"type": "input_text", "text": "x"}]}],
        )
    assert isinstance(exc_info.value, openai.APIError)


@pytest.mark.asyncio
async def test_connection_error_is_api_error_subclass():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable", request=request)

    client = _mock_client(handler)
    with pytest.raises(openai.APIConnectionError) as exc_info:
        await client.responses.create(
            model="gpt-4o-mini",
            input=[{"role": "user", "content": [{"type": "input_text", "text": "x"}]}],
        )
    assert isinstance(exc_info.value, openai.APIError)


@pytest.fixture
def gpt_assistant(room: Room, config: Config, mocker: MockerFixture) -> GPTAssistant:
    GPTAssistant.config = config
    node_data = {
        "id": "gpt-1",
        "type": "gpt_assistant",
        "api_key": "test-key",
        "model": "gpt-4o-mini",
        "instructions": "reply briefly",
        "cases": [{"id": "default", "o_connection": "end"}],
    }
    assistant = GPTAssistant(node_data, room=room, default_variables={})
    yield assistant
    GPTAssistant._CLIENTS.clear()


@pytest.mark.asyncio
async def test_gpt_assistant_upload_openai_file_uses_sdk(gpt_assistant: GPTAssistant):
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content
        return httpx.Response(200, json=FILE_OBJECT)

    client = _mock_client(handler)
    GPTAssistant._CLIENTS[gpt_assistant.api_key] = client
    gpt_assistant.client = client

    file_id = await gpt_assistant._upload_openai_file(
        file_name="doc.pdf",
        data=b"%PDF-1.4",
        mime="application/pdf",
        purpose="user_data",
    )

    assert file_id == "file-abc123"
    assert b"expires_after" in seen["body"]
    assert b"user_data" in seen["body"]


@pytest.mark.asyncio
async def test_gpt_assistant_run_assistant_uses_responses_and_output_text(
    gpt_assistant: GPTAssistant,
):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/responses")
        return httpx.Response(200, json=RESPONSE_OBJECT)

    client = _mock_client(handler)
    GPTAssistant._CLIENTS[gpt_assistant.api_key] = client
    gpt_assistant.client = client
    gpt_assistant.state.history = [
        {"role": "user", "content": [{"type": "input_text", "text": "hola"}]},
    ]
    gpt_assistant._state_loaded = True

    result = await gpt_assistant.run_assistant()

    assert result == "hola mundo"
    assert gpt_assistant.state.history[-1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_gpt_assistant_run_assistant_returns_api_error(gpt_assistant: GPTAssistant):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            json={"error": {"message": "boom", "type": "server_error", "code": None}},
        )

    client = _mock_client(handler)
    GPTAssistant._CLIENTS[gpt_assistant.api_key] = client
    gpt_assistant.client = client
    gpt_assistant._state_loaded = True

    result = await gpt_assistant.run_assistant()

    assert isinstance(result, openai.APIError)
