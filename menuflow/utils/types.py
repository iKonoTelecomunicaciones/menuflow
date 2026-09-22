from enum import Enum

from mautrix.types import SerializableEnum


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
    WEBHOOK = "webhook"


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
