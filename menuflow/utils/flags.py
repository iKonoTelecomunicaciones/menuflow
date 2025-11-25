from enum import Flag, auto


class RenderFlags(Flag):
    NONE = 0
    CONVERT_TO_TYPE = auto()
    CUSTOM_ESCAPE = auto()
    LITERAL_EVAL = auto()
    REMOVE_QUOTES = auto()
    RETURN_ERRORS = auto()
    CUSTOM_UNESCAPE = auto()
