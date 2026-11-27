from enum import Enum
from typing import Any, Literal, TypedDict

from mautrix.types import SerializableEnum

FrameStatusValue = Literal["running", "returned", "raised"]


class Nodes(SerializableEnum):
    check_time = "check_time"
    check_holiday = "check_holiday"
    email = "email"
    http_request = "http_request"
    input = "input"
    interactive_input = "interactive_input"
    invite_user = "invite_user"
    leave = "leave"
    location = "location"
    media = "media"
    message = "message"
    set_vars = "set_vars"
    subroutine = "subroutine"
    switch = "switch"
    delay = "delay"
    webhook = "webhook"
    debug = "debug"
    form = "form"
    function = "function"
    function_call = "function_call"
    function_return = "function_return"
    function_raise = "function_raise"


class Middlewares(SerializableEnum):
    JWT = "jwt"
    BASIC = "basic"
    BASE = "base"
    IRM = "irm"
    LLM = "llm"
    ASR = "asr"
    TTM = "ttm"


class Scopes(SerializableEnum):
    ROOM = "room"
    ROUTE = "route"
    NODE = "node"
    MENU = "menu"


class NodeStatus(SerializableEnum):
    ATTEMPT_EXCEEDED = "attempt_exceeded"
    DEFAULT = "default"
    TIMEOUT = "timeout"


class FrameStatus(SerializableEnum):
    RUNNING = "running"
    RETURNED = "returned"
    RAISED = "raised"


class FunctionErrors(SerializableEnum):
    MISSING_ARG = "missing_arg"
    UNEXPECTED_ARG = "unexpected_arg"
    INVALID_ARG = "invalid_arg"
    MAX_DEPTH_EXCEEDED = "max_depth_exceeded"
    FUNCTION_NOT_FOUND = "function_not_found"
    SUBROUTINE_NOT_ALLOWED = "subroutine_not_allowed"
    NOT_IN_FUNCTION = "not_in_function"
    INTERNAL_ERROR = "internal_error"
    NODE_NOT_FOUND = "node_not_found"
    MAX_NODE_ATTEMPTS = "max_node_attempts"
    ERROR = "error"


class FunctionErrorPayload(TypedDict):
    code: str
    message: str | None
    data: Any


class FunctionFrame(TypedDict):
    call_id: str
    function: str
    function_id: str
    return_to: str
    isolate: bool
    locals: dict[str, Any]
    saved_node: dict[str, Any]
    status: FrameStatusValue
    implicit: bool
    result: Any
    error: FunctionErrorPayload | None
    context: dict[str, Any]


class QueueSignal:
    LEAVE = object()
    TIMEOUT = object()
    CANCELLED = object()


class ProtectedVars(Enum):
    CURRENT_BOT_MXID = Scopes.ROOM.value + ".current_bot_mxid"
    CUSTOMER_ROOM_ID = Scopes.ROOM.value + ".customer_room_id"
    CUSTOMER_MXID = Scopes.ROOM.value + ".customer_mxid"
    PUPPET_MXID = Scopes.ROOM.value + ".puppet_mxid"
    BOT_MXID = Scopes.MENU.value + ".bot_mxid"

    @classmethod
    def is_protected(cls, variable_id: str) -> bool:
        return variable_id in _PROTECTED_VARS_SET


_PROTECTED_VARS_SET: frozenset[str] = frozenset(e.value for e in ProtectedVars)
