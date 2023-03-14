from __future__ import annotations

import logging
from typing import Dict

from mautrix.util.logging import TraceLogger

from .middlewares import HTTPMiddleware
from .nodes import CheckTime, HTTPRequest, Input, Media, Message, Switch
from .repository import Flow as FlowModel
from .room import Room


class Flow:
    log: TraceLogger = logging.getLogger("menuflow.flow")

    nodes: Dict[str, (Message, Input, Switch, HTTPRequest, CheckTime)] = {}
    middlewares: Dict[str, HTTPMiddleware] = {}

    def __init__(self, flow_data: FlowModel) -> None:
        self.data: FlowModel = flow_data.serialize()

    @property
    def flow_variables(self) -> Dict:
        return self.data.get("flow_variables", {})

    def load(self):
        self.load_middlewares()
        self.load_nodes()

    def load_nodes(self):
        """It takes the nodes from the flow data and creates a new node object for each one"""
        for node in self.data.get("nodes", []):
            if node.get("type") == "message":
                node = Message(message_node_data=node)
            elif node.get("type") == "media":
                node = Media(media_node_data=node)
            elif node.get("type") == "switch":
                node = Switch(switch_node_data=node)
            elif node.get("type") == "input":
                node = Input(input_node_data=node)
            elif node.get("type") == "check_time":
                node = CheckTime(check_time_node_data=node)
            elif node.get("type") == "http_request":
                node = HTTPRequest(http_request_node_data=node)

                if node.data.get("middleware"):
                    node.middleware = self.get_middleware_by_id(node.data.get("middleware"))
            else:
                continue

            node.variables = self.flow_variables or {}
            self.nodes[node.id] = node

    def load_middlewares(self):
        """It loads the middlewares from the data file into the `middlewares` dictionary"""
        for middleware in self.data.get("middlewares", []):
            middleware = HTTPMiddleware(http_middleware_data=middleware)
            self.middlewares[middleware.id] = middleware

    def get_node_by_id(self, node_id: str) -> HTTPRequest | Input | Message | Switch | CheckTime:
        return self.nodes.get(node_id)

    def get_middleware_by_id(self, middleware_id: str) -> HTTPMiddleware:
        return self.middlewares.get(middleware_id)

    def node(self, room: Room) -> HTTPRequest | Input | Message | Switch | CheckTime:
        """It returns the node that should be executed next

        Parameters
        ----------
        room : Room
            The room object that the user is currently in.

        Returns
        -------
            The node object.

        """
        node = self.get_node_by_id(node_id=room.node_id or "start")

        if not node:
            return

        node.room = room
        node.variables.update(room._variables)

        return node
