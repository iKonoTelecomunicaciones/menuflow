from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from .flags import RenderFlags
from .function_errors import FunctionFault
from .types import FrameStatus, FunctionErrorPayload, FunctionFrame, Scopes

if TYPE_CHECKING:
    from ..flow import Flow
    from ..room import Room


_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
}

_STRING_RENDER_FLAGS = RenderFlags.REMOVE_QUOTES

# Only the node-scope keys that must survive across a function call.
_SAVED_NODE_KEYS = ("reentry_node_attempts", "attempt")


class FunctionCaller:
    """Mixin with invoke/resume for function calls.

    The host must be a node that provides ``room``, ``id``, ``render_data``
    (typically from ``Base``), and optionally ``flow`` / ``config``.
    """

    room: Room
    flow: Flow | None
    id: str

    def _resolve_function(self, ref: str) -> dict | None:
        if self.flow is not None:
            return self.flow.get_function(ref)
        return None

    def _max_depth(self) -> int:
        config = getattr(self, "config", None) or getattr(self.room, "config", None)
        if config is None:
            return 256
        return int(config.get("menuflow.functions.max_depth", 256))

    def _validate_args(self, definition: dict, args: dict[str, Any]) -> dict[str, Any]:
        """Apply defaults, check types, and build frame locals. Raises FunctionFault."""
        params: dict = definition.get("params") or {}
        frame_locals: dict[str, Any] = {}

        for name, value in args.items():
            if name not in params:
                raise FunctionFault.unexpected_arg(name)

        for name, param in params.items():
            if not isinstance(param, dict):
                param = {}
            required = bool(param.get("required", False))
            has_default = "default" in param
            param_type = param.get("type")

            if name in args:
                value = args[name]
            elif has_default:
                value = param["default"]
            elif required:
                raise FunctionFault.missing_arg(name)
            else:
                continue

            if param_type and param_type in _TYPE_CHECKS and value is not None:
                if not _TYPE_CHECKS[param_type](value):
                    raise FunctionFault.invalid_arg(
                        message=(
                            f"Argument '{name}' expected type '{param_type}', "
                            f"got {type(value).__name__}"
                        ),
                        data={"argument": name, "expected": param_type},
                    )

            frame_locals[name] = value

        return frame_locals

    def _render_args(self, definition: dict, raw_args: dict) -> dict:
        """Render args in the caller's scope.

        String params use only ``REMOVE_QUOTES`` so values like ``00123`` stay
        strings instead of being coerced by ``CONVERT_TO_TYPE``.
        """
        if isinstance(raw_args, str):
            rendered = self.render_data(raw_args)
            if not isinstance(rendered, dict):
                raise FunctionFault.invalid_arg(
                    message="args must evaluate to a dict", data={"args": raw_args}
                )
            return rendered

        params: dict = definition.get("params") or {}
        rendered: dict[str, Any] = {}

        for name, template in (raw_args or {}).items():
            param = params.get(name) or {}
            param_type = param.get("type") if isinstance(param, dict) else None
            if param_type == "string" and isinstance(template, str):
                rendered[name] = self.render_data(template, flags=_STRING_RENDER_FLAGS)
            else:
                rendered[name] = self.render_data(template)

        return rendered

    def _snapshot_node_scope(self) -> dict[str, Any]:
        """Copy only reentry counters from the caller node scope (not full node state)."""
        node_scope = self.room.scope.get(Scopes.NODE)
        return {key: node_scope[key] for key in _SAVED_NODE_KEYS if key in node_scope}

    def new_frame(
        self,
        *,
        function: str,
        function_id: str,
        return_to: str,
        frame_locals: dict[str, Any] | None = None,
        saved_node: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        isolate: bool = False,
    ) -> FunctionFrame:
        """Build a running ``FunctionFrame`` for ``fn_stack``."""
        return FunctionFrame(
            call_id=uuid4().hex,
            function=function,
            function_id=function_id,
            return_to=return_to,
            context=context or {},
            isolate=isolate,
            locals=frame_locals or {},
            saved_node=saved_node or {},
            status=FrameStatus.RUNNING.value,  # type: ignore[typeddict-item]
            implicit=False,
            result=None,
            error=None,
        )

    async def invoke(
        self, ref: str, args: dict | None = None, context: dict | None = None
    ) -> FunctionErrorPayload | None:
        """Push a frame and jump to the function definition node.

        Startup failures (missing function, max depth, bad args) return an error
        payload without pushing a frame. On success, returns ``None``.
        """
        try:
            definition = self._resolve_function(ref)
            if not definition:
                raise FunctionFault.function_not_found(ref)

            max_depth = self._max_depth()
            if len(self.room.route.fn_stack) >= max_depth:
                raise FunctionFault.max_depth(max_depth)

            rendered_args = self._render_args(definition, args or {})
            frame_locals = self._validate_args(definition, rendered_args)
        except FunctionFault as fault:
            return fault.to_dict()

        frame = self.new_frame(
            function=definition.get("name") or definition.get("id"),
            function_id=definition.get("id"),
            return_to=self.id,
            frame_locals=frame_locals,
            saved_node=self._snapshot_node_scope(),
            context=context,
            isolate=bool(definition.get("isolate", False)),
        )
        self.room.route.push_frame(frame)
        await self.room.update_menu(node_id=definition.get("id"))
        return None

    async def resume(
        self, frame: FunctionFrame | None = None
    ) -> tuple[Any, FunctionErrorPayload | None, str | None]:
        """Consume a closed frame for this caller.

        Restores saved node counters, resolves implicit ``returns.value`` while
        the frame (and its locals) are still active, then pops the frame.
        Persistence is left to the caller's next ``update_menu``.
        """
        if frame is None:
            frame = self.room.route.find_function_frame(self.id)
        if not frame:
            return (
                None,
                FunctionFault.not_in_function("No returned frame for this caller").to_dict(),
                None,
            )

        saved_node = frame.get("saved_node") or {}
        self.room.scope.set(Scopes.NODE, dict(saved_node), use_locals=False)

        result = frame["result"]
        error = frame["error"]
        call_id = frame["call_id"]
        implicit = frame["implicit"]

        if implicit and error is None:
            definition = self._resolve_function(frame.get("function_id") or frame.get("function"))
            returns = (definition or {}).get("returns") or {}
            if isinstance(returns, dict) and "value" in returns:
                result = self.render_data(returns.get("value"))

        self.room.route.pop_frame()
        return result, error, call_id
