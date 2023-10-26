from __future__ import annotations

from datetime import datetime
from logging import getLogger

from .event_types import MenuflowEventTypes, MenuflowNodeEvents
from .node_events import NodeEntry, NodeInputData, NodeInputTimeout

log = getLogger()


def send_node_event(event_type: MenuflowNodeEvents, **kwargs):
    if event_type == MenuflowNodeEvents.NodeEntry:
        event = NodeEntry(
            event_type=MenuflowEventTypes.NODE,
            event=MenuflowNodeEvents.NodeEntry,
            timestamp=datetime.utcnow().timestamp(),
            sender=kwargs.get("sender"),
            node_type=kwargs.get("node_type"),
            node_id=kwargs.get("node_id"),
            o_connection=kwargs.get("o_connection"),
            variables=kwargs.get("variables"),
        )
    elif event_type == MenuflowNodeEvents.NodeInputData:
        event = NodeInputData(
            event_type=MenuflowEventTypes.NODE,
            event=MenuflowNodeEvents.NodeInputData,
            timestamp=datetime.utcnow().timestamp(),
            sender=kwargs.get("sender"),
            node_id=kwargs.get("node_id"),
            o_connection=kwargs.get("o_connection"),
            variables=kwargs.get("variables"),
        )
    elif event_type == MenuflowNodeEvents.NodeInputTimeout:
        event = NodeInputTimeout(
            event_type=MenuflowEventTypes.NODE,
            event=MenuflowNodeEvents.NodeInputTimeout,
            timestamp=datetime.utcnow().timestamp(),
            sender=kwargs.get("sender"),
            node_id=kwargs.get("node_id"),
            o_connection=kwargs.get("o_connection"),
            variables=kwargs.get("variables"),
        )

    event.send()
