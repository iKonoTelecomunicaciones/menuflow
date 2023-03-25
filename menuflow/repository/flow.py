from __future__ import annotations

from typing import Any, Dict, List

from attr import dataclass, ib
from mautrix.types import SerializableAttrs

from .middlewares import HTTPMiddleware
from .nodes import CheckTime, HTTPRequest, Input, Message, Switch


@dataclass
class Flow(SerializableAttrs):
    nodes: List[Message, Input, HTTPRequest, Switch, CheckTime] = ib(factory=list)
    middlewares: List[HTTPMiddleware] = ib(default=[])
    flow_variables: Dict[str, Any] = ib(default={})
