from __future__ import annotations

import logging
from typing import Any, Dict, List

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
    flow_variables: Dict[str, Any] = ib(default=None, metadata={"json": "flow_variables"})

    log: TraceLogger = logging.getLogger("menuflow.flow")

    def get_node_by_id(self, node_id: str) -> Message | Input | HTTPRequest | None:
        for node in self.nodes:
            if node_id == node.id:
                return node

    def get_middleware_by_id(self, middleware_id: str) -> HTTPMiddleware | None:
        if not self.middlewares:
            return

        for middleware in self.middlewares:
            if middleware_id == middleware.id:
                return middleware

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
        node.flow_variables = self.flow_variables

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

    def middleware(self, room: Room, middleware_id: str) -> HTTPMiddleware | None:
        """It returns the middleware object.

        Parameters
        ----------
        room : Room
            The room that the middleware is being called from.
        middleware_id : str
            The ID of the middleware you want to get.

        Returns
        -------
            A middleware object

        """

        middleware: HTTPMiddleware = self.get_middleware_by_id(middleware_id=middleware_id)

        if not middleware:
            return

        middleware.room = room
        middleware.flow_variables = self.flow_variables
        middleware = self.build_object(middleware.serialize(), HTTPMiddleware)

        return middleware
