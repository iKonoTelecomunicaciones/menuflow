from __future__ import annotations

import copy
import logging
from unittest.mock import AsyncMock, MagicMock

import nest_asyncio
import pytest
import pytest_asyncio

from menuflow.config import Config
from menuflow.flow import Flow
from menuflow.matrix import MatrixHandler
from menuflow.nodes import (
    Function,
    FunctionCall,
    FunctionRaise,
    FunctionReturn,
    Message,
    SetVars,
)
from menuflow.repository.room_events import RoomEvents
from menuflow.room import Room
from menuflow.utils.types import FunctionErrors

nest_asyncio.apply()

CRASH_FLOW_NODES = [
    {
        "id": "call_crash",
        "type": "function_call",
        "function": "crash_fn",
        "args": {},
        "cases": [
            {"id": "return", "o_connection": "m_ok"},
            {
                "id": "error",
                "o_connection": "m_error",
                "variables": {
                    "route.error_code": "{{ node.function.error.code }}",
                    "route.error_msg": "{{ node.function.error.message }}",
                },
            },
        ],
        "send_event": False,
    },
    {
        "id": "fn_crash",
        "type": "function",
        "name": "crash_fn",
        "params": {},
        "o_connection": "fn_boom",
        "send_event": False,
    },
    {
        "id": "fn_boom",
        "type": "set_vars",
        "variables": {"set": {"route.marker": "before_crash"}},
        "o_connection": "fn_return_ok",
        "send_event": False,
    },
    {
        "id": "fn_return_ok",
        "type": "function_return",
        "value": "ok",
        "send_event": False,
    },
    {"id": "m_ok", "type": "message", "text": "ok", "send_event": False},
    {"id": "m_error", "type": "message", "text": "error", "send_event": False},
    {
        "id": "call_no_error_case",
        "type": "function_call",
        "function": "crash_fn",
        "args": {},
        "cases": [{"id": "return", "o_connection": "m_ok"}],
        "send_event": False,
    },
    {
        "id": "call_missing",
        "type": "function_call",
        "function": "missing_body_fn",
        "args": {},
        "cases": [
            {"id": "return", "o_connection": "m_ok"},
            {
                "id": "error",
                "o_connection": "m_error",
                "variables": {"route.error_code": "{{ node.function.error.code }}"},
            },
        ],
        "send_event": False,
    },
    {
        "id": "fn_missing_body",
        "type": "function",
        "name": "missing_body_fn",
        "params": {},
        "o_connection": "does_not_exist",
        "send_event": False,
    },
    {
        "id": "call_nested_outer",
        "type": "function_call",
        "function": "outer_crash",
        "args": {},
        "cases": [
            {"id": "return", "o_connection": "m_ok"},
            {
                "id": "error",
                "o_connection": "m_error",
                "variables": {"route.error_code": "{{ node.function.error.code }}"},
            },
        ],
        "send_event": False,
    },
    {
        "id": "fn_outer_crash",
        "type": "function",
        "name": "outer_crash",
        "params": {},
        "o_connection": "call_nested_inner",
        "send_event": False,
    },
    {
        "id": "call_nested_inner",
        "type": "function_call",
        "function": "crash_fn",
        "args": {},
        "cases": [{"id": "return", "o_connection": "fn_outer_return"}],
        "send_event": False,
    },
    {
        "id": "fn_outer_return",
        "type": "function_return",
        "value": "outer",
        "send_event": False,
    },
    {
        "id": "plain_crash",
        "type": "set_vars",
        "variables": {"set": {"route.x": "1"}},
        "o_connection": "m_ok",
        "send_event": False,
    },
    {
        "id": "call_recurse",
        "type": "function_call",
        "function": "recurse_crash",
        "args": {"n": 1},
        "cases": [
            {"id": "return", "o_connection": "m_ok"},
            {
                "id": "error",
                "o_connection": "m_error",
                "variables": {"route.error_code": "{{ node.function.error.code }}"},
            },
        ],
        "send_event": False,
    },
    {
        "id": "fn_recurse_crash",
        "type": "function",
        "name": "recurse_crash",
        "params": {"n": {"type": "integer", "required": True}},
        "o_connection": "fn_recurse_switch",
        "send_event": False,
    },
    {
        "id": "fn_recurse_switch",
        "type": "set_vars",
        "variables": {"set": {"route.depth": "{{ route.n }}"}},
        "o_connection": "fn_recurse_call",
        "send_event": False,
    },
    {
        "id": "fn_recurse_call",
        "type": "function_call",
        "function": "recurse_crash",
        "args": {"n": 2},
        "cases": [
            {"id": "return", "o_connection": "fn_recurse_return"},
            {
                "id": "error",
                "o_connection": "fn_recurse_return",
                # room.* survives the frame pop (route.* would stay in locals)
                "variables": {"room.caught_depth": "{{ route.n }}"},
            },
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
        "id": "call_loop",
        "type": "function_call",
        "function": "loop_fn",
        "args": {},
        "cases": [
            {"id": "return", "o_connection": "m_ok"},
            {
                "id": "error",
                "o_connection": "m_error",
                "variables": {"route.error_code": "{{ node.function.error.code }}"},
            },
        ],
        "send_event": False,
    },
    {
        "id": "fn_loop",
        "type": "function",
        "name": "loop_fn",
        "params": {},
        "o_connection": "fn_loop_body",
        "send_event": False,
    },
    {
        "id": "fn_loop_body",
        "type": "set_vars",
        "variables": {"set": {"route.marker": "looping"}},
        "o_connection": "fn_loop_body",
        "send_event": False,
    },
]


@pytest_asyncio.fixture
async def crash_flow(config: Config, room: Room) -> Flow:
    room.matrix_client.set_typing = AsyncMock()
    room.matrix_client.send_message = AsyncMock()
    room.matrix_client.send_text = AsyncMock()
    room.room_events = RoomEvents()
    flow = Flow()
    await flow.load_flow(
        content={
            "flow_variables": {},
            "nodes": copy.deepcopy(CRASH_FLOW_NODES),
            "loaded_metadata": {},
        },
        config=config,
    )
    for cls in (Function, FunctionCall, FunctionReturn, FunctionRaise, Message, SetVars):
        cls.config = config
    return flow


def _make_handler(flow: Flow, config: Config) -> MatrixHandler:
    handler = object.__new__(MatrixHandler)
    handler.log = logging.getLogger("menuflow.matrix.test")
    handler.mxid = "@bot:example.com"
    handler.LOCKED_ROOMS = set()
    handler.QUEUE_MESSAGE = {}
    handler.config = config
    handler.flow = flow
    handler.MAX_NODE_ATTEMPTS = config.get("menuflow.max_node_attempts", 64)
    handler.flow_sync = MagicMock()
    handler.flow_sync.check_active_tag = AsyncMock()
    handler.lock_room = MagicMock()
    handler.unlock_room = MagicMock()
    handler.update_room_events = AsyncMock()
    return handler


class BoomSetVars(SetVars):
    async def run(self):
        raise RuntimeError("intentional boom")


def _patch_boom_on(mocker, node_id: str = "fn_boom"):
    original_node = Flow.node

    def node_with_boom(self, room=None):
        node = original_node(self, room)
        if node and node.id == node_id:
            return BoomSetVars(node.content, room=room, default_variables=self.flow_variables)
        return node

    mocker.patch.object(Flow, "node", node_with_boom)


@pytest.mark.asyncio
async def test_algorithm_exception_inside_function_goes_to_error_case(
    crash_flow: Flow, room: Room, config: Config, mocker
):
    _patch_boom_on(mocker, "fn_boom")

    room.route.node_id = "call_crash"
    handler = _make_handler(crash_flow, config)
    await handler.algorithm(room=room)

    # Message without o_connection ends the flow (END -> start), but the error
    # case must have run first and persisted the error variables.
    assert room.route.fn_stack == []
    assert await room.get_variable("route.error_code") == FunctionErrors.INTERNAL_ERROR.value
    assert "intentional boom" in (await room.get_variable("route.error_msg") or "")


@pytest.mark.asyncio
async def test_algorithm_unhandled_function_error_goes_to_start(
    crash_flow: Flow, room: Room, config: Config, mocker
):
    _patch_boom_on(mocker, "fn_boom")

    room.route.node_id = "call_no_error_case"
    handler = _make_handler(crash_flow, config)
    await handler.algorithm(room=room)

    assert room.route.node_id == "start"
    assert room.route.fn_stack == []
    assert await room.get_variable("route.error_code") is None


@pytest.mark.asyncio
async def test_algorithm_missing_node_inside_function(
    crash_flow: Flow, room: Room, config: Config
):
    room.route.node_id = "call_missing"
    handler = _make_handler(crash_flow, config)
    await handler.algorithm(room=room)

    assert room.route.fn_stack == []
    assert await room.get_variable("route.error_code") == FunctionErrors.NODE_NOT_FOUND.value


@pytest.mark.asyncio
async def test_algorithm_nested_propagates_when_inner_has_no_error_case(
    crash_flow: Flow, room: Room, config: Config, mocker
):
    _patch_boom_on(mocker, "fn_boom")

    room.route.node_id = "call_nested_outer"
    handler = _make_handler(crash_flow, config)
    await handler.algorithm(room=room)

    assert room.route.fn_stack == []
    assert await room.get_variable("route.error_code") == FunctionErrors.INTERNAL_ERROR.value


@pytest.mark.asyncio
async def test_algorithm_exception_outside_function_goes_to_start(
    crash_flow: Flow, room: Room, config: Config, mocker
):
    _patch_boom_on(mocker, "plain_crash")

    room.route.node_id = "plain_crash"
    handler = _make_handler(crash_flow, config)
    await handler.algorithm(room=room)

    assert room.route.node_id == "start"
    assert room.route.fn_stack == []
    assert await room.get_variable("route.error_code") is None


@pytest.mark.asyncio
async def test_algorithm_recursive_error_caught_by_previous_depth(
    crash_flow: Flow, room: Room, config: Config, mocker
):
    """Depth 2 crashes; recursive function_call has error case -> depth 1 handles it."""
    original_node = Flow.node
    crash_depths: list[int] = []

    def node_with_conditional_boom(self, room=None):
        node = original_node(self, room)
        if node and node.id == "fn_recurse_switch":
            frame_locals = room.route.current_frame["locals"] if room.route.current_frame else {}
            n = frame_locals.get("n")
            if n == 2:
                crash_depths.append(n)

                class BoomAtDepth(SetVars):
                    async def run(self):
                        raise RuntimeError(f"crash at depth {n}")

                return BoomAtDepth(node.content, room=room, default_variables=self.flow_variables)
        return node

    mocker.patch.object(Flow, "node", node_with_conditional_boom)

    room.route.node_id = "call_recurse"
    handler = _make_handler(crash_flow, config)
    await handler.algorithm(room=room)

    assert crash_depths == [2]
    assert room.route.fn_stack == []
    assert await room.get_variable("room.caught_depth") == 1
    assert await room.get_variable("route.error_code") is None


@pytest.mark.asyncio
async def test_algorithm_max_node_attempts_inside_function(
    crash_flow: Flow, room: Room, config: Config
):
    room.route.node_id = "call_loop"
    handler = _make_handler(crash_flow, config)
    handler.MAX_NODE_ATTEMPTS = 3
    room.config["menuflow"]["max_node_attempts"] = 3

    await handler.algorithm(room=room)

    assert room.route.fn_stack == []
    assert await room.get_variable("route.error_code") == FunctionErrors.MAX_NODE_ATTEMPTS.value
