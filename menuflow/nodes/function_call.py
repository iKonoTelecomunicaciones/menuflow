from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..db.route import RouteState
from ..repository import FunctionCall as FunctionCallModel
from ..room import Room
from ..utils.function_caller import FunctionCaller
from ..utils.function_errors import FunctionFault
from ..utils.types import FunctionErrorPayload, FunctionErrors
from ..utils.util import Util
from .switch import Switch

if TYPE_CHECKING:
    from ..flow import Flow


_NO_TARGET = (None, "", "finish")


class FunctionCall(FunctionCaller, Switch):

    def __init__(
        self,
        function_call_node_data: FunctionCallModel,
        room: Room,
        default_variables: dict,
        flow: Flow | None = None,
    ) -> None:
        Switch.__init__(
            self,
            switch_node_data=function_call_node_data,
            room=room,
            default_variables=default_variables,
        )
        self.log = self.log.getChild(function_call_node_data.get("id"))
        self.content: dict = function_call_node_data
        self.flow = flow

    @property
    def function_ref(self) -> str:
        return self.render_data(self.content.get("function", ""))

    @property
    def raw_args(self) -> dict:
        return self.content.get("args") or {}

    @property
    def variables(self) -> dict:
        return self.content.get("variables") or {}

    def _resolve_variables(self, result: Any) -> dict:
        """Resolve jq expressions against a function return value.

        Unlike ``resolve_response_variables``, accepts any JSON value (including
        scalars) so ``route.x: .`` stores the result as-is.
        """
        mapping = self.variables
        if not mapping:
            return {}

        resolved: dict = {}
        for name, expression in mapping.items():
            jq_result = Util.jq_compile(expression, result)
            if jq_result.get("status") != 200:
                self.log.error(
                    f"[{self.room.room_id}] Error parsing '{expression}' with jq "
                    f"on variable '{name}'. Set to None. "
                    f"Error message: {jq_result.get('error')}, Status: {jq_result.get('status')}"
                )
                resolved[name] = None
                continue

            data_match = jq_result.get("result") or []
            resolved[name] = (
                data_match if len(data_match) > 1 else (data_match[0] if data_match else None)
            )

        return resolved

    async def _first_case(self, *case_ids: str) -> str | None:
        """Pick the first listed case with a real ``o_connection``; load only its variables."""
        cases = await self.load_cases()
        for case_id in case_ids:
            case_result = cases.get(case_id)
            if case_result is None:
                continue
            conn = self.render_data(case_result.get("o_connection"))
            if conn in _NO_TARGET:
                continue
            await self.load_variables(case_result.get("variables", {}))
            return conn
        return None

    async def _route_result(
        self, result: Any, error: FunctionErrorPayload | None, call_id: str | None
    ) -> None:
        """Publish ``node.function``, follow return/error cases, then advance the menu.

        Unhandled errors (no ``error``/``default`` case) raise ``FunctionFault`` so
        ``FunctionRecovery`` can bubble to an outer caller or fall back to start.
        """
        self.room.set_node_var(function={"result": result, "error": error, "call_id": call_id})

        if error:
            o_connection = await self._first_case("error", "default")
            if o_connection is None:
                raise FunctionFault(
                    code=error.get("code", FunctionErrors.ERROR.value),
                    message=(
                        f"Unhandled function error in '{self.id}': "
                        f"{error.get('code')}: {error.get('message')}"
                    ),
                    data=error.get("data"),
                    node_id=self.id,
                )
        else:
            o_connection = await self._first_case("return", "default")
            if o_connection is None:
                o_connection = await self.get_o_connection()

        if self.variables and result is not None:
            resolved = self._resolve_variables(result)
            if resolved:
                await self.room.set_variables(variables=resolved)

        await self.room.update_menu(
            node_id=o_connection,
            state=RouteState.END if not o_connection else None,
        )

        await self._send_node_event(o_connection=o_connection)

    async def run(self) -> None:
        self.log.info(f"[{self.room.room_id}] Entering function_call node {self.id}")

        returned_frame = self.room.route.find_function_frame(self.id)
        if returned_frame:
            result, error, call_id = await self.resume(returned_frame)
            await self._route_result(result, error, call_id)
            return

        error = await self.invoke(ref=self.function_ref, args=self.raw_args)
        if error:
            await self._route_result(result=None, error=error, call_id=None)
