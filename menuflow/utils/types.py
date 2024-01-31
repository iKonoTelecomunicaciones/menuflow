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
    jwt = "jwt"
    basic = "basic"
    base = "base"
    irm = "irm"
