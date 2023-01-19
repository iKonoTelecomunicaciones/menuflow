from __future__ import annotations

import logging
from typing import Dict, List

from attr import dataclass, ib
from mautrix.types import SerializableAttrs
from mautrix.util.logging import TraceLogger

from .middlewares.http import HTTPMiddleware
from .nodes import HTTPRequest, Input, Message, Switch
from .room import Room


@dataclass
class Flow(SerializableAttrs):

    nodes: List[Message, Input, HTTPRequest] = ib(metadata={"json": "nodes"}, factory=list)
    middelwares: List[HTTPMiddleware] = ib(default=None, metadata={"json": "middelwares"})

    log: TraceLogger = logging.getLogger("menuflow.flow")

    def get_node_by_id(self, node_id: str) -> Message | Input | HTTPRequest | None:
        for node in self.nodes:
            if node_id == node.id:
                return node

    def get_middleware_by_id(self, middleware_id: str) -> HTTPMiddleware | None:
        for middleware in self.middelwares:
            if middleware_id == middleware.id:
                return middleware

    def build_node(
        self, data: Dict, type_class: Message | Input | HTTPRequest | Switch | None
    ) -> Message | Input | HTTPRequest | Switch | None:
        return type_class.deserialize(data)

    def node(self, room: Room) -> Message | Input | HTTPRequest | None:

        node = self.get_node_by_id(node_id=room.node_id)

        if not node:
            return

        node.room = room

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

    def build_middleware(
        self, data: Dict, type_class: HTTPMiddleware | None
    ) -> HTTPMiddleware | None:
        return type_class.deserialize(data)

    def _middlewares(self, room: Room) -> List[HTTPMiddleware] | None:
        middlewares: List[HTTPMiddleware] = []
        for middleware in self.middelwares:
            middleware.room = room
            middleware = self.build_middleware(middleware.serialize(), HTTPMiddleware)
            middlewares.append(middleware)
        return middlewares
