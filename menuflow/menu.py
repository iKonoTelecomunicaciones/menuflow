from __future__ import annotations

from typing import List, Optional

from attr import dataclass, ib

from mautrix.types import SerializableAttrs

from .node import HTTPRequest, Input, Message
from .utils.base_logger import BaseLogger
from .variable import Variable


@dataclass
class Menu(SerializableAttrs, BaseLogger):
    id: str = ib(metadata={"json": "id"})
    global_variables: Optional[List[Variable]] = ib(
        metadata={"json": "global_variables"}, factory=list
    )
    nodes: List[Message, Input, HTTPRequest] = ib(metadata={"json": "nodes"}, factory=list)

    def get_node_by_id(self, node_id: str) -> Message | Input | HTTPRequest | None:
        for node in self.nodes:
            if node_id == node.id:
                return node
