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
    middlewares: List[HTTPMiddleware] = ib(default=None, metadata={"json": "middlewares"})

    log: TraceLogger = logging.getLogger("menuflow.flow")

    def get_node_by_id(self, node_id: str) -> Message | Input | HTTPRequest | None:
        for node in self.nodes:
            if node_id == node.id:
                return node

    def build_object(
        self,
        data: Dict,
        type_class: Message | Input | HTTPRequest | Switch | HTTPMiddleware | None,
    ) -> Message | Input | HTTPRequest | Switch | HTTPMiddleware | None:
        """It takes a dictionary of data and a class, and returns an instance of that class

        Parameters
        ----------
        data : Dict
            The data to deserialize.
        type_class : Message | Input | HTTPRequest | Switch | HTTPMiddleware | None
            The class of the middleware to be built.

        Returns
        -------
            A deserialized instance of the type_class.

        """
        return type_class.deserialize(data)

    def node(self, room: Room) -> Message | Input | HTTPRequest | None:

        node = self.get_node_by_id(node_id=room.node_id)

        if not node:
            return

        node.room = room

        if node.type == "message":
            node = self.build_object(node.serialize(), Message)
        elif node.type == "input":
            node = self.build_object(node.serialize(), Input)
        elif node.type == "http_request":
            node = self.build_object(node.serialize(), HTTPRequest)
        elif node.type == "switch":
            node = self.build_object(node.serialize(), Switch)
        else:
            return

        return node

    def _middlewares(self, room: Room) -> List[HTTPMiddleware] | None:
        """A function that returns a list of middlewares.

        Parameters
        ----------
        room : Room
            Room

        Returns
        -------
            A list of middlewares

        """

        middlewares: List[HTTPMiddleware] = []
        for middleware in self.middlewares:
            middleware.room = room
            middleware = self.build_object(middleware.serialize(), HTTPMiddleware)
            middlewares.append(middleware)
        return middlewares
