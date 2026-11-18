from __future__ import annotations

import nest_asyncio
import pytest

from menuflow.function_recovery import FunctionFaultNode, FunctionRecovery
from menuflow.room import Room
from menuflow.utils.function_errors import FunctionFault
from menuflow.utils.types import FrameStatus, FunctionErrors

nest_asyncio.apply()


@pytest.mark.asyncio
async def test_unwind_without_frames_returns_false(room: Room):
    handled = await FunctionRecovery.unwind(
        room=room,
        failing_node_id="x",
        code=FunctionErrors.INTERNAL_ERROR.value,
        message="boom",
    )
    assert handled is False
    assert room.route.fn_stack == []


@pytest.mark.asyncio
async def test_unwind_running_frame_raises_to_caller(room: Room):
    room.route.push_frame(
        {
            "call_id": "1",
            "status": FrameStatus.RUNNING.value,
            "isolate": False,
            "locals": {},
            "return_to": "call_customer",
            "result": None,
            "error": None,
        }
    )
    room.route.node_id = "fn_body"

    handled = await FunctionRecovery.unwind(
        room=room,
        failing_node_id="fn_body",
        code=FunctionErrors.INTERNAL_ERROR.value,
        message="boom",
        data={"node_id": "fn_body"},
    )

    assert handled is True
    assert room.route.node_id == "call_customer"
    frame = room.route.current_frame
    assert frame["status"] == FrameStatus.RAISED.value
    assert frame["error"]["code"] == FunctionErrors.INTERNAL_ERROR.value
    assert frame["error"]["message"] == "boom"


@pytest.mark.asyncio
async def test_unwind_caller_failure_pops_and_raises_outer(room: Room):
    room.route.push_frame(
        {
            "call_id": "outer",
            "status": FrameStatus.RUNNING.value,
            "isolate": False,
            "locals": {},
            "return_to": "call_outer",
            "result": None,
            "error": None,
        }
    )
    room.route.push_frame(
        {
            "call_id": "inner",
            "status": FrameStatus.RETURNED.value,
            "isolate": False,
            "locals": {},
            "return_to": "call_inner",
            "result": {"ok": True},
            "error": None,
        }
    )
    room.route.node_id = "call_inner"

    handled = await FunctionRecovery.unwind(
        room=room,
        failing_node_id="call_inner",
        code=FunctionErrors.INTERNAL_ERROR.value,
        message="caller failed",
    )

    assert handled is True
    assert len(room.route.fn_stack) == 1
    assert room.route.node_id == "call_outer"
    assert room.route.current_frame["status"] == FrameStatus.RAISED.value
    assert room.route.current_frame["error"]["message"] == "caller failed"


@pytest.mark.asyncio
async def test_unwind_keeps_result_after_return_side_effect(room: Room):
    room.route.push_frame(
        {
            "call_id": "1",
            "status": FrameStatus.RETURNED.value,
            "isolate": False,
            "locals": {},
            "return_to": "call_customer",
            "result": {"name": "Ana"},
            "error": None,
        }
    )
    room.route.node_id = "fn_return_ok"

    handled = await FunctionRecovery.unwind(
        room=room,
        failing_node_id="fn_return_ok",
        code=FunctionErrors.INTERNAL_ERROR.value,
        message="event failed",
    )

    assert handled is True
    assert room.route.node_id == "call_customer"
    assert room.route.current_frame["status"] == FrameStatus.RETURNED.value
    assert room.route.current_frame["result"] == {"name": "Ana"}


@pytest.mark.asyncio
async def test_unwind_pops_all_when_top_caller_fails(room: Room):
    room.route.push_frame(
        {
            "call_id": "1",
            "status": FrameStatus.RETURNED.value,
            "isolate": False,
            "locals": {},
            "return_to": "call_customer",
            "result": None,
            "error": {"code": "x", "message": "y", "data": None},
        }
    )
    room.route.node_id = "call_customer"

    handled = await FunctionRecovery.unwind(
        room=room,
        failing_node_id="call_customer",
        code=FunctionErrors.INTERNAL_ERROR.value,
        message="unhandled at top",
    )

    assert handled is False
    assert room.route.fn_stack == []


def test_intercept_without_frames_returns_none(room: Room):
    room.route.node_id = "missing"
    assert FunctionRecovery.intercept(room, None) is None
    assert FunctionRecovery.intercept(room, {"id": "x", "type": "message"}) is None


def test_intercept_missing_node_inside_function(room: Room):
    room.route.push_frame(
        {
            "call_id": "1",
            "status": FrameStatus.RUNNING.value,
            "isolate": False,
            "locals": {},
            "return_to": "call_customer",
            "result": None,
            "error": None,
        }
    )
    room.route.node_id = "does_not_exist"

    fault_node = FunctionRecovery.intercept(room, None)
    assert isinstance(fault_node, FunctionFaultNode)
    assert fault_node.fault.code == FunctionErrors.NODE_NOT_FOUND.value
    assert fault_node.fault.node_id is None


def test_intercept_max_attempts_inside_function(room: Room):
    room.route.push_frame(
        {
            "call_id": "1",
            "status": FrameStatus.RUNNING.value,
            "isolate": False,
            "locals": {},
            "return_to": "call_customer",
            "result": None,
            "error": None,
        }
    )
    room.route.node_id = "loop_node"
    max_attempts = int(room.config.get("menuflow.max_node_attempts", 64))
    room.set_node_var(reentry_node_attempts=max_attempts)

    fault_node = FunctionRecovery.intercept(room, {"id": "loop_node", "type": "message"})
    assert isinstance(fault_node, FunctionFaultNode)
    assert fault_node.fault.code == FunctionErrors.MAX_NODE_ATTEMPTS.value
    assert fault_node.fault.node_id == "loop_node"


@pytest.mark.asyncio
async def test_recover_function_fault_uses_typed_fields(room: Room):
    room.route.push_frame(
        {
            "call_id": "1",
            "status": FrameStatus.RUNNING.value,
            "isolate": False,
            "locals": {},
            "return_to": "call_customer",
            "result": None,
            "error": None,
        }
    )
    room.route.node_id = "fn_body"
    fault = FunctionFault.max_attempts("fn_body")

    handled = await FunctionRecovery.recover(room=room, node=None, error=fault)

    assert handled is True
    assert room.route.node_id == "call_customer"
    assert room.route.current_frame["error"]["code"] == FunctionErrors.MAX_NODE_ATTEMPTS.value
