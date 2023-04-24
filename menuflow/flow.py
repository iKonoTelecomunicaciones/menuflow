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
    nodes_by_id: Dict[str, Dict] = {}
    middlewares_by_id: Dict[str, Dict] = {}

    def __init__(self, flow_data: FlowModel) -> None:
        self.data: FlowModel = (
            flow_data.serialize() if isinstance(flow_data, SerializableAttrs) else flow_data
        )
        self.nodes = self.data.get("nodes", [])
        self.middlewares = self.data.get("middlewares", [])

    def _add_node_to_cache(self, node_data: Dict):
        self.nodes_by_id[node_data.get("id")] = node_data

    def _add_middleware_to_cache(self, node_data: Dict):
        self.nodes_by_id[node_data.get("id")] = node_data

    @property
    def flow_variables(self) -> Dict:
        return self.data.get("flow_variables", {})

    def get_node_by_id(self, node_id: str) -> Dict:
        node = self.nodes_by_id.get(node_id)
        if node:
            return node

        for node in self.nodes:
            if node_id == node.get("id", ""):
                self._add_node_to_cache(node)
                return node

        return None

    def get_middleware_by_id(self, middleware_id):
        middleware = self.middlewares_by_id.get(middleware_id)
        if middleware:
            return middleware

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
            node_initialiced = Message(message_node_data=node_data)
        elif node_data.get("type") == "media":
            node_initialiced = Media(media_node_data=node_data)
        elif node_data.get("type") == "email":
            node_initialiced = Email(email_node_data=node_data)
        elif node_data.get("type") == "location":
            node_initialiced = Location(location_node_data=node_data)
        elif node_data.get("type") == "switch":
            node_initialiced = Switch(switch_node_data=node_data)
        elif node_data.get("type") == "input":
            node_initialiced = Input(input_node_data=node_data)
        elif node_data.get("type") == "check_time":
            node_initialiced = CheckTime(check_time_node_data=node_data)
        elif node_data.get("type") == "http_request":
            node_initialiced = HTTPRequest(http_request_node_data=node_data)

            if node_data.get("middleware"):
                middleware = self.middleware(node_data.get("middleware"), room)
                node_initialiced.middleware = middleware
        else:
            return

        node_initialiced.room = room
        node_initialiced.variables = self.flow_variables or {}
        node_initialiced.variables.update(room._variables)

        return node_initialiced
