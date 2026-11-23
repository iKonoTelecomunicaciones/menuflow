from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .nodes.base import Base
from .utils.function_errors import FunctionFault
from .utils.types import FunctionErrors

if TYPE_CHECKING:
    from .room import Room


class FunctionFaultNode(Base):
    """Virtual node that raises FunctionFault inside the algorithm try block.

    ``Flow.node()`` / ``intercept`` run outside the algorithm ``try``, so a
    typed failure must be deferred until ``node.run()`` executes inside it.
    """

    def __init__(self, room: Room, fault: FunctionFault) -> None:
        Base.__init__(self, room=room, default_variables={})
        self.fault = fault
        self.content = {"id": fault.node_id or room.route.node_id or "", "type": "function_fault"}

    async def run(self) -> None:
        raise self.fault


class FunctionRecovery:
    """Deliver algorithm failures to the nearest function caller, or signal fallback to start."""

    @staticmethod
    def intercept(room: Room, node_data: dict | None) -> FunctionFaultNode | None:
        """While inside a function, trap missing destinations or max reentry loops.

        Returns a deferred ``FunctionFaultNode`` when ``fn_stack`` is non-empty and
        the next node is missing or looping; otherwise ``None``.
        """
        if not room.route.fn_stack:
            return None

        if node_data is None:
            return FunctionFaultNode(
                room=room, fault=FunctionFault.node_not_found(room.route.node_id)
            )

        config = getattr(room, "config", None)
        # Keep the same default as MatrixHandler.MAX_NODE_ATTEMPTS.
        max_attempts = int(config.get("menuflow.max_node_attempts", 255)) if config else 255
        if room.reentry_node_attempts >= max_attempts:
            return FunctionFaultNode(
                room=room,
                fault=FunctionFault.max_attempts(room.route.node_id),
            )

        return None

    @classmethod
    async def recover(cls, room: Room, node: Any, error: BaseException) -> bool:
        """Map an algorithm exception to ``unwind``.

        ``FunctionFault`` keeps its typed fields; other exceptions become
        ``internal_error``. Returns True if a caller should continue, False to
        fall back to ``RouteState.ERROR`` / start.
        """
        if isinstance(error, FunctionFault):
            return await cls.unwind(
                room=room,
                failing_node_id=error.node_id,
                code=error.code,
                message=error.message,
                data=error.data,
            )

        node_id = getattr(node, "id", None) if node is not None else None
        return await cls.unwind(
            room=room,
            failing_node_id=node_id,
            code=FunctionErrors.INTERNAL_ERROR.value,
            message=str(error),
            data={"node_id": node_id, "exception": type(error).__name__},
        )

    @staticmethod
    async def unwind(
        room: Room,
        failing_node_id: str | None,
        code: str,
        message: str | None = None,
        data: Any = None,
    ) -> bool:
        """Raise toward the caller, or preserve a closed frame's result.

        - Running frame: ``fn_raise`` and continue.
        - Closed frame and failure at the caller: pop and try the outer frame.
        - Closed frame and failure still inside the callee (e.g. event after
          ``function_return``): keep result/error and ensure ``node_id`` is
          ``return_to``.
        """
        frame = room.route.current_frame
        if not frame:
            return False

        if room.route.is_running(frame):
            await room.fn_raise(code=code, message=message, data=data)
            return True

        # Frame already returned or raised. If the caller itself failed while
        # consuming its frame, or return_to no longer exists, pop and try outer.
        if failing_node_id is None or failing_node_id == frame.get("return_to"):
            room.route.pop_frame()
            outer = room.route.current_frame
            if not outer:
                await room.route.update_variables()
                return False
            if room.route.is_running(outer):
                await room.fn_raise(code=code, message=message, data=data)
                return True
            return False

        # Failure after marking the return (e.g. send_node_event on
        # function_return). Keep the result and ensure we are on return_to.
        if room.route.node_id != frame.get("return_to"):
            await room.update_menu(node_id=frame["return_to"])
        return True
