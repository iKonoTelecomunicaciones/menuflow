from enum import Enum

from .check_time import CheckTime
from .flow_object import FlowObject
from .http_request import HTTPRequest
from .input import Input
from .message import Message
from .switch import Switch


class NodeType(Enum):
    MESSAGE = "message"
    SWITCH = "switch"
    INPUT = "input"
    HTTPREQUEST = "http_request"
    CHECKTIME = "check_time"
