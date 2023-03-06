from __future__ import annotations

import logging
from typing import Any, Dict, List

from attr import dataclass, ib
from mautrix.types import SerializableAttrs
from mautrix.util.logging import TraceLogger

from .middlewares.http import HTTPMiddleware
from .nodes import CheckTime, FlowObject, HTTPRequest, Input, Message, Switch, avilable_nodes


@dataclass
class Flow(SerializableAttrs):

    nodes: List[Message, Input, HTTPRequest, Switch, CheckTime] = ib(factory=list)
    middlewares: List[HTTPMiddleware] = ib(default=None)
    flow_variables: Dict[str, Any] = ib(default=None)

    nodes_by_id: Dict[str, FlowObject] = {}
    middlewares_by_id: Dict[str, HTTPMiddleware] = {}

    log: TraceLogger = logging.getLogger("menuflow.flow")

    def _add_to_cache(self, obj: FlowObject | HTTPMiddleware):
        if isinstance(obj, HTTPMiddleware):
            self.middlewares_by_id[obj.id] = obj
        elif isinstance(obj, FlowObject):
            self.nodes_by_id[obj.id] = obj

    def get_node_by_id(
        self, node_id: str
    ) -> Message | Input | HTTPRequest | Switch | CheckTime | None:
        try:
            return self.nodes_by_id[node_id]
        except KeyError:
            pass

        for node in self.nodes:
            if node_id == node.id:
                node = self.node(node.serialize())
                self._add_to_cache(node)
                return node

    def get_middleware_by_id(self, middleware_id: str) -> HTTPMiddleware | None:
        if not self.middlewares:
            return

        try:
            return self.middlewares_by_id[middleware_id]
        except KeyError:
            pass

        for middleware in self.middlewares:
            if middleware_id == middleware.id:
                self._add_to_cache(middleware)
                return middleware

    def build_object(
        self,
        data: Dict,
        type_class: Message | Input | HTTPRequest | Switch | HTTPMiddleware | CheckTime | None,
    ) -> Message | Input | HTTPRequest | Switch | HTTPMiddleware | CheckTime | None:
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

    def node(self, node_data: Dict) -> Message | Input | HTTPRequest | Switch | CheckTime | None:

        if not node_data:
            return

        node_type = node_data.get("type", "")

        return self.build_object(node_data, avilable_nodes.get(node_type))

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
