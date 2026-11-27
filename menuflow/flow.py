from __future__ import annotations

import logging
from typing import Any, Union

from mautrix.util.logging import TraceLogger

from .config import Config
from .flow_utils import FlowUtils
from .function_recovery import FunctionRecovery
from .middlewares import ASRMiddleware, HTTPMiddleware, IRMMiddleware, LLMMiddleware, TTMMiddleware
from .nodes import (
    CheckHoliday,
    CheckTime,
    Debug,
    Delay,
    Email,
    FormInput,
    Function,
    FunctionCall,
    FunctionRaise,
    FunctionReturn,
    GPTAssistant,
    HTTPRequest,
    Input,
    InteractiveInput,
    InviteUser,
    Leave,
    Location,
    Media,
    Message,
    SetVars,
    Subroutine,
    Switch,
    Webhook,
)
from .repository import Flow as FlowModel
from .room import Room
from .utils import Middlewares, Util

Node = Union[
    CheckTime,
    Email,
    HTTPRequest,
    Input,
    InteractiveInput,
    InviteUser,
    Leave,
    Location,
    Media,
    Message,
    SetVars,
    Subroutine,
    Switch,
    Delay,
    GPTAssistant,
    FormInput,
    Webhook,
    Debug,
    Function,
    FunctionCall,
    FunctionReturn,
    FunctionRaise,
]


class Flow:
    flow_utils: FlowUtils
    log: TraceLogger = logging.getLogger("menuflow.flow")

    def __init__(self) -> None:
        self.data: Flow = None
        self.nodes: list[dict] = []
        self.nodes_by_id: dict[str, dict] = {}
        self.functions_by_name: dict[str, dict] = {}

    @property
    def flow_variables(self) -> dict:
        return {"flow": self.data.flow_variables or {}}

    @classmethod
    def init_cls(cls, flow_utils: FlowUtils) -> None:
        cls.flow_utils = flow_utils

    async def load_flow(
        self,
        flow_mxid: str | None = None,
        content: dict | None = None,
        config: Config | None = None,
    ) -> Flow:
        self.data = await FlowModel.load_flow(flow_mxid=flow_mxid, content=content, config=config)
        self.nodes = self.data.nodes or []
        self.nodes_by_id: dict[str, dict] = {}
        self.functions_by_name = self._build_functions_by_name(self.nodes)
        errors, warnings = self.validate_functions(self.nodes)
        for error in errors:
            self.log.error("Function validation: %s", error)
        for warning in warnings:
            self.log.warning("Function validation: %s", warning)

    @staticmethod
    def _build_functions_by_name(nodes: list[dict]) -> dict[str, dict]:
        functions: dict[str, dict] = {}
        for node in nodes or []:
            if node.get("type") != "function":
                continue
            name = node.get("name")
            if name:
                functions[name] = node
        return functions

    def get_function(self, ref: str) -> dict | None:
        """Resolve a ``type: function`` node by ``name``, falling back to node id."""
        if not ref:
            return None
        if fn := self.functions_by_name.get(ref):
            return fn
        node = self.get_node_by_id(ref)
        if node and node.get("type") == "function":
            return node
        return None

    @classmethod
    def validate_functions(cls, nodes: list[dict]) -> tuple[list[str], list[str]]:
        """Static checks: required ``name``, unique names, subroutine reachability warnings."""
        errors: list[str] = []
        warnings: list[str] = []
        seen_names: dict[str, str] = {}
        nodes = nodes or []
        nodes_by_id = {n.get("id"): n for n in nodes if n.get("id")}

        for node in nodes:
            if node.get("type") != "function":
                continue
            node_id = node.get("id", "")
            name = node.get("name")
            if not name:
                errors.append(f"Function node '{node_id}' is missing required field 'name'")
                continue
            if name in seen_names:
                errors.append(
                    f"Duplicate function name '{name}' in nodes "
                    f"'{seen_names[name]}' and '{node_id}'"
                )
            else:
                seen_names[name] = node_id

            warning = cls._subroutine_warning_in_body(node, nodes_by_id)
            if warning:
                warnings.append(warning)

        return errors, warnings

    @classmethod
    def _subroutine_warning_in_body(
        cls, function_node: dict, nodes_by_id: dict[str, dict]
    ) -> str | None:
        """Return a warning if a subroutine is reachable via literal connections."""
        start = function_node.get("o_connection")
        if not cls._is_literal(start):
            return None

        visited: set[str] = set()
        pending = [start]
        while pending:
            node_id = pending.pop()
            if node_id in visited or node_id in ("", "finish"):
                continue
            visited.add(node_id)
            node = nodes_by_id.get(node_id)
            if not node:
                continue
            if node.get("type") == "subroutine":
                return (
                    f"Function '{function_node.get('name')}' ({function_node.get('id')}) "
                    f"can reach subroutine '{node_id}' via literal connections; "
                    f"subroutine is not allowed inside a function at runtime"
                )
            if node.get("type") in ("function", "function_return", "function_raise"):
                continue
            for target in cls._literal_connections(node):
                if target not in visited:
                    pending.append(target)
        return None

    @staticmethod
    def _is_literal(conn: Any) -> bool:
        return isinstance(conn, str) and bool(conn) and "{{" not in conn

    @classmethod
    def _literal_connections(cls, node: dict) -> list[str]:
        targets: list[str] = []
        for conn in (
            node.get("o_connection"),
            *(case.get("o_connection") for case in node.get("cases") or []),
            node.get("go_sub"),
        ):
            if cls._is_literal(conn):
                targets.append(conn)
        return targets

    def _add_node_to_cache(self, node_data: dict):
        self.nodes_by_id[node_data.get("id")] = node_data

    def get_node_by_id(self, node_id: str) -> dict | None:
        """This function returns a node from a cache or a list of nodes based on its ID.

        Parameters
        ----------
        node_id : str
            The ID of the node that we want to retrieve from the graph.

        Returns
        -------
            This function returns a dictionary object representing a node in a graph, or `None`
            if the node with the given ID is not found.

        """

        try:
            return self.nodes_by_id[node_id]
        except KeyError:
            pass

        for node in self.nodes:
            if node_id == node.get("id", ""):
                self._add_node_to_cache(node)
                return node

    def middleware(
        self, middleware_id: str, room: Room
    ) -> HTTPMiddleware | IRMMiddleware | ASRMiddleware | None:
        middleware_model = self.flow_utils.get_middleware_by_id(middleware_id=middleware_id)
        try:
            middleware_type = Middlewares(middleware_model.type)
        except ValueError:
            self.log.warning(f"Middleware type {middleware_model.type} not found")
            return

        if not middleware_model:
            return

        if middleware_type in (Middlewares.JWT, Middlewares.BASIC, Middlewares.BASE):
            middleware_initialized = HTTPMiddleware(
                http_middleware_data=middleware_model,
                room=room,
                default_variables=self.flow_variables,
            )
        elif middleware_type == Middlewares.IRM:
            middleware_initialized = IRMMiddleware(
                irm_data=middleware_model, room=room, default_variables=self.flow_variables
            )
        elif middleware_type == Middlewares.LLM:
            middleware_initialized = LLMMiddleware(
                llm_data=middleware_model, room=room, default_variables=self.flow_variables
            )
        elif middleware_type == Middlewares.ASR:
            middleware_initialized = ASRMiddleware(
                asr_middleware_content=middleware_model,
                room=room,
                default_variables=self.flow_variables,
            )
        elif middleware_type == Middlewares.TTM:
            middleware_initialized = TTMMiddleware(
                ttm_data=middleware_model, room=room, default_variables=self.flow_variables
            )

        return middleware_initialized

    def node(self, room: Room) -> Node | None:
        node_data = self.get_node_by_id(node_id=room.route.node_id)

        if fault_node := FunctionRecovery.intercept(room, node_data):
            return fault_node

        if not node_data:
            return

        if node_data.get("type") == "message":
            node_initialized = Message(
                message_node_data=node_data, room=room, default_variables=self.flow_variables
            )
        elif node_data.get("type") == "media":
            node_initialized = Media(
                media_node_data=node_data, room=room, default_variables=self.flow_variables
            )
            if node_data.get("middleware"):
                middleware = self.middleware(node_data.get("middleware"), room)
                node_initialized.middleware = middleware
        elif node_data.get("type") == "email":
            node_initialized = Email(
                email_node_data=node_data, room=room, default_variables=self.flow_variables
            )
        elif node_data.get("type") == "location":
            node_initialized = Location(
                location_node_data=node_data, room=room, default_variables=self.flow_variables
            )
        elif node_data.get("type") == "switch":
            node_initialized = Switch(
                switch_node_data=node_data, room=room, default_variables=self.flow_variables
            )
        elif node_data.get("type") == "input":
            node_initialized = Input(
                input_node_data=node_data, room=room, default_variables=self.flow_variables
            )
            if node_data.get("middlewares"):
                middlewares = []
                for middleware in node_data.get("middlewares"):
                    middlewares.append(self.middleware(middleware, room=room))
                node_initialized.middlewares = middlewares
        elif node_data.get("type") == "check_time":
            node_initialized = CheckTime(
                check_time_node_data=node_data, room=room, default_variables=self.flow_variables
            )
        elif node_data.get("type") == "check_holiday":
            node_initialized = CheckHoliday(
                check_holiday_data=node_data, room=room, default_variables=self.flow_variables
            )
        elif node_data.get("type") == "http_request":
            node_initialized = HTTPRequest(
                http_request_node_data=node_data, room=room, default_variables=self.flow_variables
            )

            if node_data.get("middleware"):
                middleware = self.middleware(node_data.get("middleware"), room)
                node_initialized.middleware = middleware
        elif node_data.get("type") in ("interactive_input", "interactive_form_input"):
            node_initialized = InteractiveInput(
                interactive_input_data=node_data, room=room, default_variables=self.flow_variables
            )
        elif node_data.get("type") == "leave":
            node_initialized = Leave(
                leave_node_data=node_data, room=room, default_variables=self.flow_variables
            )
        elif node_data.get("type") == "set_vars":
            node_initialized = SetVars(
                set_vars_node_data=node_data, room=room, default_variables=self.flow_variables
            )
        elif node_data.get("type") == "invite_user":
            node_initialized = InviteUser(
                invite_node_data=node_data, room=room, default_variables=self.flow_variables
            )
        elif node_data.get("type") == "subroutine":
            node_initialized = Subroutine(
                subroutine_node_data=node_data, room=room, default_variables=self.flow_variables
            )
        elif node_data.get("type") == "delay":
            node_initialized = Delay(
                delay_node_data=node_data, room=room, default_variables=self.flow_variables
            )
        elif node_data.get("type") == "gpt_assistant":
            node_initialized = GPTAssistant(
                gpt_assistant_node_data=node_data,
                room=room,
                default_variables=self.flow_variables,
            )

            if node_data.get("middlewares"):
                middlewares = []
                for middleware in node_data.get("middlewares"):
                    middlewares.append(self.middleware(middleware, room=room))
                node_initialized.middlewares = middlewares
        elif node_data.get("type") == "form":
            node_initialized = FormInput(
                form_node_data=node_data, room=room, default_variables=self.flow_variables
            )
        elif node_data.get("type") == "webhook":
            node_initialized = Webhook(
                webhook_data=node_data, room=room, default_variables=self.flow_variables
            )
        elif node_data.get("type") == "debug":
            node_initialized = Debug(
                debug_node_data=node_data, room=room, default_variables=self.flow_variables
            )
        elif node_data.get("type") == "function":
            node_initialized = Function(
                function_node_data=node_data, room=room, default_variables=self.flow_variables
            )
        elif node_data.get("type") == "function_call":
            node_initialized = FunctionCall(
                function_call_node_data=node_data,
                room=room,
                default_variables=self.flow_variables,
                flow=self,
            )
        elif node_data.get("type") == "function_return":
            node_initialized = FunctionReturn(
                function_return_node_data=node_data,
                room=room,
                default_variables=self.flow_variables,
            )
        elif node_data.get("type") == "function_raise":
            node_initialized = FunctionRaise(
                function_raise_node_data=node_data,
                room=room,
                default_variables=self.flow_variables,
            )
        else:
            return

        return node_initialized
