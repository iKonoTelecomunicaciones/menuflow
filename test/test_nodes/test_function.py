from __future__ import annotations

import copy
from unittest.mock import AsyncMock

import nest_asyncio
import pytest
import pytest_asyncio

from menuflow.config import Config
from menuflow.db.route import RouteState
from menuflow.flow import Flow
from menuflow.function_recovery import FunctionRecovery
from menuflow.nodes import (
    Function,
    FunctionCall,
    FunctionRaise,
    FunctionReturn,
    Input,
    Message,
    SetVars,
    Subroutine,
    Switch,
)
from menuflow.room import Room
from menuflow.utils.function_errors import FunctionFault
from menuflow.utils.types import FrameStatus, FunctionErrors, Scopes

nest_asyncio.apply()


FUNCTION_FLOW_NODES = [
    {
        "id": "call_customer",
        "type": "function_call",
        "function": "get_customer",
        "args": {"document": "{{ route.document }}"},
        "variables": {"route.customer": ".", "route.customer_name": ".name"},
        "cases": [
            {"id": "return", "o_connection": "m_ok"},
            {
                "id": "error",
                "o_connection": "m_error",
                "variables": {"route.error_msg": "{{ node.function.error.message }}"},
            },
        ],
        "send_event": False,
    },
    {
        "id": "fn_get_customer",
        "type": "function",
        "name": "get_customer",
        "params": {
            "document": {"type": "string", "required": True},
            "include_invoices": {"type": "boolean", "default": False},
        },
        "returns": {"type": "object", "value": {"name": "{{ route.customer_name }}"}},
        "o_connection": "fn_set_customer",
        "send_event": False,
    },
    {
        "id": "fn_set_customer",
        "type": "set_vars",
        "variables": {"set": {"route.customer_name": "Ana"}},
        "o_connection": "fn_return_ok",
        "send_event": False,
    },
    {
        "id": "fn_return_ok",
        "type": "function_return",
        "value": {"name": "Ana", "document": "{{ route.document }}"},
        "send_event": False,
    },
    {
        "id": "fn_raise_not_found",
        "type": "function_raise",
        "code": "not_found",
        "message": "Cliente {{ route.document }} no encontrado",
        "send_event": False,
    },
    {"id": "m_ok", "type": "message", "text": "ok", "send_event": False},
    {"id": "m_error", "type": "message", "text": "error", "send_event": False},
    {
        "id": "fn_implicit",
        "type": "function",
        "name": "implicit_fn",
        "params": {},
        "returns": {"value": {"ok": True, "doc": "{{ route.document }}"}},
        "o_connection": "fn_implicit_body",
        "send_event": False,
    },
    {
        "id": "fn_implicit_body",
        "type": "set_vars",
        "variables": {"set": {}},
        "o_connection": "",
        "send_event": False,
    },
    {
        "id": "call_implicit",
        "type": "function_call",
        "function": "implicit_fn",
        "args": {},
        "variables": {"route.implicit_result": "."},
        "cases": [{"id": "return", "o_connection": "m_ok"}],
        "send_event": False,
    },
    {
        "id": "fn_nested_outer",
        "type": "function",
        "name": "outer",
        "params": {"document": {"type": "string", "required": True}},
        "o_connection": "fn_call_inner",
        "send_event": False,
    },
    {
        "id": "fn_call_inner",
        "type": "function_call",
        "function": "inner",
        "args": {"document": "{{ route.document }}"},
        "variables": {"route.inner_result": "."},
        "cases": [{"id": "return", "o_connection": "fn_return_outer"}],
        "send_event": False,
    },
    {
        "id": "fn_return_outer",
        "type": "function_return",
        "value": {"outer": "{{ route.document }}", "inner": "{{ route.inner_result }}"},
        "send_event": False,
    },
    {
        "id": "fn_nested_inner",
        "type": "function",
        "name": "inner",
        "params": {"document": {"type": "string", "required": True}},
        "o_connection": "fn_return_inner",
        "send_event": False,
    },
    {
        "id": "fn_return_inner",
        "type": "function_return",
        "value": "inner-{{ route.document }}",
        "send_event": False,
    },
    {
        "id": "call_outer",
        "type": "function_call",
        "function": "outer",
        "args": {"document": "{{ route.document }}"},
        "variables": {"route.nested": "."},
        "cases": [{"id": "return", "o_connection": "m_ok"}],
        "send_event": False,
    },
    {
        "id": "fn_recurse",
        "type": "function",
        "name": "recurse",
        "params": {"n": {"type": "integer", "required": True}},
        "o_connection": "fn_recurse_call",
        "send_event": False,
    },
    {
        "id": "fn_recurse_call",
        "type": "function_call",
        "function": "recurse",
        "args": {"n": "{{ route.n }}"},
        "cases": [
            {"id": "return", "o_connection": "fn_recurse_return"},
            {"id": "error", "o_connection": "fn_recurse_raise_depth"},
        ],
        "send_event": False,
    },
    {
        "id": "fn_recurse_return",
        "type": "function_return",
        "value": "{{ route.n }}",
        "send_event": False,
    },
    {
        "id": "fn_recurse_raise_depth",
        "type": "function_raise",
        "code": "max_depth_exceeded",
        "message": "depth exceeded",
        "send_event": False,
    },
    {
        "id": "call_recurse",
        "type": "function_call",
        "function": "recurse",
        "args": {"n": 1},
        "cases": [
            {"id": "return", "o_connection": "m_ok"},
            {"id": "error", "o_connection": "m_error"},
        ],
        "send_event": False,
    },
    {
        "id": "fn_with_sub",
        "type": "function",
        "name": "with_sub",
        "params": {},
        "o_connection": "fn_sub",
        "send_event": False,
    },
    {
        "id": "fn_sub",
        "type": "subroutine",
        "go_sub": "somewhere",
        "o_connection": "fn_return_ok",
        "send_event": False,
    },
    {
        "id": "call_with_sub",
        "type": "function_call",
        "function": "with_sub",
        "args": {},
        "cases": [
            {"id": "return", "o_connection": "m_ok"},
            {
                "id": "error",
                "o_connection": "m_error",
                "variables": {"route.error_msg": "{{ node.function.error.message }}"},
            },
        ],
        "send_event": False,
    },
    {
        "id": "fn_input_body",
        "type": "function",
        "name": "ask_doc",
        "params": {},
        "o_connection": "fn_input",
        "send_event": False,
    },
    {
        "id": "fn_input",
        "type": "input",
        "text": "doc?",
        "variable": "route.document",
        "cases": [{"id": "default", "o_connection": "fn_return_input"}],
        "send_event": False,
    },
    {
        "id": "fn_return_input",
        "type": "function_return",
        "value": "{{ route.document }}",
        "send_event": False,
    },
    {
        "id": "call_ask_doc",
        "type": "function_call",
        "function": "ask_doc",
        "args": {},
        "variables": {"route.asked": "."},
        "cases": [{"id": "return", "o_connection": "m_ok"}],
        "send_event": False,
    },
    {
        "id": "fn_depth",
        "type": "function",
        "name": "depth",
        "params": {"n": {"type": "integer", "required": True}},
        "o_connection": "depth_sw",
        "send_event": False,
    },
    {
        "id": "depth_sw",
        "type": "switch",
        "validation": "{% if (route.n | int) <= 0 %}stop{% else %}go{% endif %}",
        "cases": [
            {"id": "go", "o_connection": "depth_prompt"},
            {"id": "stop", "o_connection": "depth_done"},
            {"id": "default", "o_connection": "depth_done"},
        ],
        "send_event": False,
    },
    {
        "id": "depth_done",
        "type": "function_return",
        "value": "0",
        "send_event": False,
    },
    {
        "id": "depth_prompt",
        "type": "input",
        "text": "n={{ route.n }}",
        "variable": "_",
        "cases": [{"id": "default", "o_connection": "depth_dec"}],
        "send_event": False,
    },
    {
        "id": "depth_dec",
        "type": "set_vars",
        "variables": {"set": {"route.next": "{% set x = route.n | int - 1 %}{{ x }}"}},
        "o_connection": "depth_call_inner",
        "send_event": False,
    },
    {
        "id": "depth_call_inner",
        "type": "function_call",
        "function": "depth",
        "args": {"n": "{{ route.next }}"},
        "variables": {"route.step": "."},
        "cases": [{"id": "return", "o_connection": "depth_join"}],
        "send_event": False,
    },
    {
        "id": "depth_join",
        "type": "function_return",
        "value": "{{ route.n }}>{{ route.step }}",
        "send_event": False,
    },
    {
        "id": "call_depth",
        "type": "function_call",
        "function": "depth",
        "args": {"n": 3},
        "variables": {"route.depth_result": "."},
        "cases": [
            {"id": "return", "o_connection": "m_ok"},
            {"id": "error", "o_connection": "m_error"},
        ],
        "send_event": False,
    },
]


@pytest_asyncio.fixture
async def function_flow(config: Config, room: Room) -> Flow:
    room.matrix_client.set_typing = AsyncMock()
    room.matrix_client.send_message = AsyncMock()
    room.matrix_client.send_text = AsyncMock()
    flow = Flow()
    await flow.load_flow(
        content={
            "flow_variables": {},
            "nodes": copy.deepcopy(FUNCTION_FLOW_NODES),
            "loaded_metadata": {},
        },
        config=config,
    )
    for cls in (
        Function,
        FunctionCall,
        FunctionReturn,
        FunctionRaise,
        Message,
        Input,
        Subroutine,
        SetVars,
        Switch,
    ):
        cls.config = config
    room.route.node_id = "call_customer"
    return flow


async def _run_until(flow: Flow, room: Room, stop_ids: set[str], max_steps: int = 40) -> list[str]:
    """Run the current node repeatedly until node_id is in stop_ids or END/ERROR."""
    visited: list[str] = []
    for _ in range(max_steps):
        if room.route.node_id in stop_ids:
            break
        if room.route.state in (RouteState.END, RouteState.ERROR):
            break
        if room.route.state == RouteState.INPUT:
            break
        node = flow.node(room)
        if node is None:
            break
        visited.append(node.id)
        try:
            if isinstance(node, Input):
                await node.run(None)
            else:
                await node.run()
        except Exception as e:
            if not await FunctionRecovery.recover(room=room, node=node, error=e):
                room.route.state = RouteState.ERROR
                break
            continue
        if room.route.node_id == visited[-1] and room.route.state != RouteState.INPUT:
            # No progress
            break
    return visited


async def _run_with_inputs(
    flow: Flow, room: Room, replies: list[str], stop_ids: set[str], max_steps: int = 80
) -> list[str]:
    """Like _run_until, but feed replies whenever the route is waiting on INPUT."""
    pending = list(replies)
    visited: list[str] = []
    for _ in range(max_steps):
        if room.route.node_id in stop_ids:
            break
        if room.route.state in (RouteState.END, RouteState.ERROR):
            break
        if room.route.state == RouteState.INPUT:
            if not pending:
                break
            node = flow.node(room)
            assert isinstance(node, Input)
            text = pending.pop(0)
            room.set_node_var(content=text)
            await node.input_text(text=text)
            continue
        chunk = await _run_until(flow, room, stop_ids, max_steps=max_steps)
        if not chunk:
            break
        visited.extend(chunk)
    return visited


@pytest.mark.asyncio
async def test_call_return_variable_and_jq(function_flow: Flow, room: Room):
    await room.set_variable("route.document", "123")
    await _run_until(function_flow, room, {"m_ok", "m_error"})

    assert room.route.node_id == "m_ok"
    assert room.route.fn_stack == []
    customer = await room.get_variable("route.customer")
    assert customer["name"] == "Ana"
    assert str(customer["document"]) == "123"
    assert await room.get_variable("route.customer_name") == "Ana"


@pytest.mark.asyncio
async def test_function_raise_routes_to_error(function_flow: Flow, room: Room):
    # Redirect body to raise
    fn = function_flow.get_node_by_id("fn_get_customer")
    fn["o_connection"] = "fn_raise_not_found"

    await room.set_variable("route.document", "999")
    await _run_until(function_flow, room, {"m_ok", "m_error"})

    assert room.route.node_id == "m_error"
    assert await room.get_variable("route.error_msg") == "Cliente 999 no encontrado"
    assert room.route.fn_stack == []


@pytest.mark.asyncio
async def test_implicit_return_renders_returns_value(function_flow: Flow, room: Room):
    room.route.node_id = "call_implicit"
    await room.set_variable("route.document", "ABC", use_locals=False)
    await _run_until(function_flow, room, {"m_ok", "m_error"})

    assert room.route.node_id == "m_ok"
    result = await room.get_variable("route.implicit_result")
    assert result == {"ok": True, "doc": "ABC"}


@pytest.mark.asyncio
async def test_nested_function_calls(function_flow: Flow, room: Room):
    room.route.node_id = "call_outer"
    await room.set_variable("route.document", "42")
    await _run_until(function_flow, room, {"m_ok", "m_error"})

    assert room.route.node_id == "m_ok"
    nested = await room.get_variable("route.nested")
    assert str(nested["outer"]) == "42"
    assert nested["inner"] == "inner-42"
    assert room.route.fn_stack == []


@pytest.mark.asyncio
async def test_max_depth_exceeded(function_flow: Flow, room: Room, config: Config):
    config["menuflow.functions.max_depth"] = 2
    room.route.node_id = "call_recurse"
    await _run_until(function_flow, room, {"m_ok", "m_error"})

    assert room.route.node_id == "m_error"
    assert room.route.fn_stack == []


@pytest.mark.asyncio
async def test_missing_required_arg(function_flow: Flow, room: Room):
    call = function_flow.get_node_by_id("call_customer")
    call["args"] = {}
    await _run_until(function_flow, room, {"m_ok", "m_error"})

    assert room.route.node_id == "m_error"
    assert "Missing required" in (await room.get_variable("route.error_msg") or "")


@pytest.mark.asyncio
async def test_string_arg_keeps_leading_zeros(function_flow: Flow, room: Room):
    await room.set_variable("route.document", "00123")
    await _run_until(function_flow, room, {"m_ok", "m_error"})

    customer = await room.get_variable("route.customer")
    assert customer["document"] == "00123"


@pytest.mark.asyncio
async def test_saved_node_restored(function_flow: Flow, room: Room):
    room.set_node_var(
        gpt_state={"history": [{"role": "user"}]},
        reentry_node_attempts=3,
        attempt=2,
    )
    await room.set_variable("route.document", "1")

    node = function_flow.node(room)
    assert isinstance(node, FunctionCall)
    error = await node.invoke(ref=node.function_ref, args=node.raw_args)
    assert error is None
    assert room.route.current_frame is not None
    # Only counter keys are snapshotted (not the full node scope).
    assert room.route.current_frame["saved_node"] == {
        "reentry_node_attempts": 3,
        "attempt": 2,
    }
    assert "gpt_state" not in room.route.current_frame["saved_node"]

    # Jump to return directly
    room.route.node_id = "fn_return_ok"
    ret = function_flow.node(room)
    await ret.run()
    assert room.route.node_id == "call_customer"
    assert room.route.current_frame["status"] == FrameStatus.RETURNED.value

    call = function_flow.node(room)
    result, err, _call_id = await call.resume()
    node_scope = room.scope.get(Scopes.NODE)
    assert node_scope["reentry_node_attempts"] == 3
    assert node_scope["attempt"] == 2
    assert "gpt_state" not in node_scope
    assert err is None
    assert result["name"] == "Ana"


@pytest.mark.asyncio
async def test_subroutine_not_allowed_inside_function(function_flow: Flow, room: Room):
    room.route.node_id = "call_with_sub"
    await _run_until(function_flow, room, {"m_ok", "m_error"})

    assert room.route.node_id == "m_error"
    assert await room.get_variable("route.error_msg")


@pytest.mark.asyncio
async def test_function_return_outside_function_raises(function_flow: Flow, room: Room):
    room.route.node_id = "fn_return_ok"
    room.route.fn_stack = []
    node = function_flow.node(room)
    with pytest.raises(FunctionFault):
        await node.run()


@pytest.mark.asyncio
async def test_input_inside_function_persists_frame(function_flow: Flow, room: Room):
    room.route.node_id = "call_ask_doc"
    await _run_until(function_flow, room, set())

    assert room.route.state == RouteState.INPUT
    assert room.route.node_id == "fn_input"
    assert len(room.route.fn_stack) == 1
    assert room.route.current_frame["function"] == "ask_doc"
    assert room.route.current_frame["status"] == FrameStatus.RUNNING.value
    assert not room.route.current_frame.get("implicit")

    # Simulate persistence round-trip
    import json

    room.route.fn_stack = json.loads(json.dumps(room.route.fn_stack))
    room.route.variables = json.loads(json.dumps(room.route.variables))

    input_node = function_flow.node(room)
    assert isinstance(input_node, Input)
    await input_node.input_text(text="xyz")
    await _run_until(function_flow, room, {"m_ok", "m_error"})

    assert room.route.node_id == "m_ok"
    assert await room.get_variable("route.asked") == "xyz"


@pytest.mark.asyncio
async def test_recursive_function_with_input(function_flow: Flow, room: Room):
    """Input inside a recursive function must not close the frame on prompt."""
    room.route.node_id = "call_depth"
    await _run_with_inputs(
        function_flow, room, replies=["a", "a", "a"], stop_ids={"m_ok", "m_error"}
    )

    assert room.route.node_id == "m_ok"
    assert room.route.fn_stack == []
    assert await room.get_variable("route.depth_result") == "3>2>1>0"


@pytest.mark.asyncio
async def test_scope_shadow_read_write_and_isolate(room: Room):
    await room.set_variable("route.name", "global", use_locals=False)
    room.route.push_frame(
        {
            "call_id": "1",
            "status": FrameStatus.RUNNING.value,
            "isolate": False,
            "locals": {"document": "local-doc"},
            "return_to": "caller",
        }
    )

    assert await room.get_variable("route.document") == "local-doc"
    assert await room.get_variable("route.name") == "global"

    await room.set_variable("route.name", "local-name")
    assert room.route.current_frame["locals"]["name"] == "local-name"
    assert room.route.variables["route"]["name"] == "global"

    await room.set_variable("route.api_only", "x", use_locals=False)
    assert room.route.variables["route"]["api_only"] == "x"
    assert "api_only" not in room.route.current_frame["locals"]

    room.route.current_frame["isolate"] = True
    assert await room.get_variable("route.name") == "local-name"
    # global-only key not visible when isolated
    assert await room.get_variable("route.api_only") is None

    await room.del_variable("route.document")
    assert "document" not in room.route.current_frame["locals"]
    assert room.route.variables["route"].get("name") == "global"


@pytest.mark.asyncio
async def test_propagate_error_without_cases(function_flow: Flow, room: Room):
    outer_call = {
        "id": "call_propagate",
        "type": "function_call",
        "function": "get_customer",
        "args": {},
        "cases": [{"id": "return", "o_connection": "m_ok"}],
        "send_event": False,
    }
    function_flow.nodes.append(outer_call)
    function_flow.nodes_by_id["call_propagate"] = outer_call
    room.route.node_id = "call_propagate"

    # Missing args -> error, no error/default case -> FunctionFault at top level
    with pytest.raises(FunctionFault, match="Unhandled function error"):
        node = function_flow.node(room)
        await node.run()
