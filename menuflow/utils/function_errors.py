from __future__ import annotations

from typing import Any

from .types import FunctionErrorPayload, FunctionErrors


class FunctionFault(Exception):
    """Typed failure that ``FunctionRecovery`` can deliver to a function caller.

    ``node_id`` identifies where the fault originated (used by ``unwind`` when
    deciding whether the failure happened at the caller vs inside the callee).
    """

    def __init__(
        self, code: str, message: str | None = None, data: Any = None, node_id: str | None = None
    ) -> None:
        self.code = code
        self.message = message
        self.data = data
        self.node_id = node_id
        super().__init__(message or code)

    def to_dict(self) -> FunctionErrorPayload:
        """Serialize to the frame / ``node.function.error`` payload shape."""
        return FunctionErrorPayload(code=self.code, message=self.message, data=self.data)

    @classmethod
    def node_not_found(cls, node_id: str | None) -> FunctionFault:
        return cls(
            code=FunctionErrors.NODE_NOT_FOUND.value,
            message=f"Node '{node_id}' not found",
            data={"node_id": node_id},
            node_id=None,
        )

    @classmethod
    def max_attempts(cls, node_id: str | None) -> FunctionFault:
        return cls(
            code=FunctionErrors.MAX_NODE_ATTEMPTS.value,
            message=f"Maximum node attempts exceeded in '{node_id}'",
            data={"node_id": node_id},
            node_id=node_id,
        )

    @classmethod
    def not_in_function(cls, message: str | None = None) -> FunctionFault:
        _code = FunctionErrors.NOT_IN_FUNCTION.value
        return cls(code=_code, message=message or _code)

    @classmethod
    def frame_mismatch(cls, function_id: str) -> FunctionFault:
        return cls(
            code=FunctionErrors.NOT_IN_FUNCTION.value,
            message=f"Active frame does not match function '{function_id}'",
            data={"function_id": function_id},
        )

    @classmethod
    def subroutine_not_allowed(cls, subroutine_id: str) -> FunctionFault:
        return cls(
            code=FunctionErrors.SUBROUTINE_NOT_ALLOWED.value,
            message=f"Subroutine '{subroutine_id}' is not allowed inside a function",
            data={"subroutine_id": subroutine_id},
            node_id=subroutine_id,
        )

    @classmethod
    def function_not_found(cls, ref: str) -> FunctionFault:
        return cls(
            code=FunctionErrors.FUNCTION_NOT_FOUND.value,
            message=f"Function '{ref}' not found",
            data={"function": ref},
        )

    @classmethod
    def max_depth(cls, max_depth: int) -> FunctionFault:
        return cls(
            code=FunctionErrors.MAX_DEPTH_EXCEEDED.value,
            message=f"Function call depth exceeded (max {max_depth})",
            data={"max_depth": max_depth},
        )

    @classmethod
    def missing_arg(cls, name: str) -> FunctionFault:
        return cls(
            code=FunctionErrors.MISSING_ARG.value,
            message=f"Missing required argument '{name}'",
            data={"argument": name},
        )

    @classmethod
    def unexpected_arg(cls, name: str) -> FunctionFault:
        return cls(
            code=FunctionErrors.UNEXPECTED_ARG.value,
            message=f"Unexpected argument '{name}'",
            data={"argument": name},
        )

    @classmethod
    def invalid_arg(
        cls, message: str, data: dict | None = None, argument: str | None = None
    ) -> FunctionFault:
        payload = data or ({"argument": argument} if argument is not None else None)
        return cls(code=FunctionErrors.INVALID_ARG.value, message=message, data=payload)
