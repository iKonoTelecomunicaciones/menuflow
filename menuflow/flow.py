from __future__ import annotations

import logging
from typing import Dict, List

from attr import dataclass, ib
from mautrix.types import SerializableAttrs
from mautrix.util.logging import TraceLogger

from .nodes import HTTPRequest, Input, Message, Switch


@dataclass
class Flow(SerializableAttrs):

    id: str = ib(metadata={"json": "id"})
    nodes: List[Message, Input, HTTPRequest] = ib(metadata={"json": "nodes"}, factory=list)

    log: TraceLogger = logging.getLogger("menuflow.flow")

    def get_node_by_id(self, node_id: str) -> Message | Input | HTTPRequest | None:
        for node in self.nodes:
            if node_id == node.id:
                return node

    def build_node(
        self, data: Dict, type_class: Message | Input | HTTPRequest | None
    ) -> Message | Input | HTTPRequest | None:
        return type_class.deserialize(data)

    def node(self, context: str) -> Message | Input | HTTPRequest | None:

        node = self.get_node_by_id(node_id=context)

        if not node:
            return

        if node.type == "message":
            node = self.build_node(node.serialize(), Message)
        elif node.type == "input":
            node = self.build_node(node.serialize(), Input)
        elif node.type == "http_request":
            node = self.build_node(node.serialize(), HTTPRequest)
        elif node.type == "switch":
            node = self.build_node(node.serialize(), Switch)
        else:
            return

        return node
