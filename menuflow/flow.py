from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List

from mautrix.types import SerializableAttrs
from mautrix.util.logging import TraceLogger

from .middlewares import HTTPMiddleware
from .nodes import CheckTime, Email, HTTPRequest, Input, Location, Media, Message, Switch
from .repository import Flow as FlowModel
from .room import Room


class Flow:
    log: TraceLogger = logging.getLogger("menuflow.flow")

    nodes: List[Dict]
    middlewares: List[Dict]

    def __init__(self, flow_data: FlowModel) -> None:
        self.data: FlowModel = (
            flow_data.serialize() if isinstance(flow_data, SerializableAttrs) else flow_data
        )
        self.nodes = self.data.get("nodes", [])
        self.middlewares = self.data.get("middlewares", [])
        self.nodes_by_id: Dict[str, Dict] = {}
        self.middlewares_by_id: Dict[str, Dict] = {}

    def _add_node_to_cache(self, node_data: Dict):
        self.nodes_by_id[node_data.get("id")] = node_data

    def _add_middleware_to_cache(self, middleware_data: Dict):
        self.middlewares_by_id[middleware_data.get("id")] = middleware_data

    @property
    def flow_variables(self) -> Dict:
        return self.data.get("flow_variables", {})

    def get_node_by_id(self, node_id: str) -> Dict | None:
        """This function returns a node from a cache or a list of nodes based on its ID.

        Parameters
        ----------
        node_id : str
            The ID of the node that we want to retrieve from the graph.

        Returns
        -------
            This function returns a dictionary object representing a node in a graph, or `None`
            if the node with the given ID is not found.

        """

        try:
            return self.nodes_by_id[node_id]
        except KeyError:
            pass

        for node in self.nodes:
            if node_id == node.get("id", ""):
                self._add_node_to_cache(node)
                return node

    def get_middleware_by_id(self, middleware_id: str) -> Dict | None:
        """This function retrieves a middleware by its ID from a cache or a list of middlewares.

        Parameters
        ----------
        middleware_id : str
            A string representing the ID of the middleware that needs to be retrieved.

        Returns
        -------
            This function returns a dictionary object representing a middleware in a graph, or `None`
            if the node with the given ID is not found.

        """

        try:
            return self.middlewares_by_id[middleware_id]
        except KeyError:
            pass

        for middleware in self.middlewares:
            if middleware_id == middleware.get("id", ""):
                self._add_middleware_to_cache(middleware)
                return middleware

    def middleware(self, middleware_id: str, room: Room) -> HTTPMiddleware:
        middleware_data = self.get_middleware_by_id(middleware_id=middleware_id)

        if not middleware_data:
            return

        middleware_initialized = HTTPMiddleware(http_middleware_data=middleware_data)
        middleware_initialized.room = room

        return middleware_initialized

    def node(
        self, room: Room
    ) -> Message | Input | HTTPRequest | Switch | CheckTime | Media | Email | Location | None:
        node_data = self.get_node_by_id(node_id=room.node_id)

        if not node_data:
            return

        if node_data.get("type") == "message":
            node_initialized = Message(message_node_data=node_data)
        elif node_data.get("type") == "media":
            node_initialized = Media(media_node_data=node_data)
        elif node_data.get("type") == "email":
            node_initialized = Email(email_node_data=node_data)
        elif node_data.get("type") == "location":
            node_initialized = Location(location_node_data=node_data)
        elif node_data.get("type") == "switch":
            node_initialized = Switch(switch_node_data=node_data)
        elif node_data.get("type") == "input":
            node_initialized = Input(input_node_data=node_data)
        elif node_data.get("type") == "check_time":
            node_initialized = CheckTime(check_time_node_data=node_data)
        elif node_data.get("type") == "http_request":
            node_initialized = HTTPRequest(http_request_node_data=node_data)

            if node_data.get("middleware"):
                middleware = self.middleware(node_data.get("middleware"), room)
                node_initialized.middleware = middleware
        else:
            return

        node_initialized.room = room

        return node_initialized
