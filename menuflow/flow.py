from __future__ import annotations

import logging
from typing import Dict

from mautrix.util.logging import TraceLogger

from .nodes import Message
from .nodes_repository import Flow as FlowR
from .room import Room


class Flow:
    log: TraceLogger = logging.getLogger("menuflow.flow")

    nodes: Dict[str, Message] = {}

    def __init__(self, flow_data: FlowR) -> None:
        self.data: Dict = flow_data.serialize()

    @property
    def flow_variables(self) -> Dict:
        return self.data.get("flow_variables")

    def load_nodes(self):
        for node in self.data.get("nodes"):
            if node.get("type") == "message":
                self.nodes[node.get("id")] = Message(
                    message_node_data=node, variables=self.data.get("flow_variable")
                )

    def get_node_by_id(self, node_id: str) -> Message:
        return self.nodes.get(node_id)

    def node(self, room: Room) -> Message:
        node = self.get_node_by_id(node_id=room.node_id or "start")

        if not node:
            return

        node.variables.update(room._variables)
        return node
