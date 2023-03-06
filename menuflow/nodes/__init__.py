from .check_time import CheckTime
from .flow_object import FlowObject, NodeType
from .http_request import HTTPRequest
from .input import Input
from .message import Message
from .switch import Switch

avilable_nodes = {
    "message": Message,
    "input": Input,
    "http_request": HTTPRequest,
    "switch": Switch,
    "check_time": CheckTime,
}
