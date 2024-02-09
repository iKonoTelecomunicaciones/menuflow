from mautrix.types import SerializableEnum


class Nodes(SerializableEnum):
    check_time = "check_time"
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


class Middlewares(SerializableEnum):
    JWT = "jwt"
    BASIC = "basic"
    BASE = "base"
    IRM = "irm"
    LLM = "llm"
    ASR = "asr"
