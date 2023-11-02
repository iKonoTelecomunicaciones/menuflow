from mautrix.types import SerializableEnum


class Nodes(SerializableEnum):
    message = "message"
    switch = "switch"
    input = "input"
    http_request = "http_request"
    email = "email"
    check_time = "check_time"
    interactive_input = "interactive_input"
    location = "location"
    media = "media"
