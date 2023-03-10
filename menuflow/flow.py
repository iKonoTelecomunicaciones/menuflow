from __future__ import annotations

import logging
from typing import Dict

from mautrix.util.logging import TraceLogger

from .nodes import Input, Message, Switch
from .nodes_repository import Flow as FlowR
from .room import Room


class Flow:
    log: TraceLogger = logging.getLogger("menuflow.flow")

    nodes: Dict[str, Message] = {}

    def __init__(self, flow_data: FlowR) -> None:
        self.data: FlowR = flow_data

    @property
    def flow_variables(self) -> Dict:
        return self.data.flow_variables.__dict__

    def load_nodes(self):
        for node in self.data.nodes:
            if node.type == "message":
                node = Message(message_node_data=node)
            elif node.type == "switch":
                node = Switch(switch_node_data=node)
            elif node.type == "input":
                node = Input(input_node_data=node)

            node.variables = self.flow_variables or {}
            self.nodes[node.id] = node

    def get_node_by_id(self, node_id: str) -> Message:
        return self.nodes.get(node_id)

    def node(self, room: Room) -> Message:
        node = self.get_node_by_id(node_id=room.node_id or "start")

        if not node:
            return

        node.room = room
        node.variables.update(room._variables)

        return node
