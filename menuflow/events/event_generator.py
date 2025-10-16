from __future__ import annotations

from datetime import datetime, timezone
from logging import getLogger
from typing import Optional

from ..config import Config
from .event_types import MenuflowEventTypes, MenuflowNodeEvents
from .node_events import NodeEntry, NodeInputData, NodeInputTimeout

log = getLogger()


async def send_node_event(
    event_type: MenuflowNodeEvents, config: Config, send_event: Optional[bool] = None, **kwargs
):
    general_send_event = config["events.send_events"]
    send_node_event = send_event if send_event is not None else general_send_event
    if not send_node_event:
        return

    if event_type == MenuflowNodeEvents.NodeEntry:
        event = NodeEntry(
            event_type=MenuflowEventTypes.NODE,
            event=MenuflowNodeEvents.NodeEntry,
            timestamp=datetime.now(timezone.utc).timestamp(),
            room_id=kwargs.get("room_id"),
            sender=kwargs.get("sender"),
            node_type=kwargs.get("node_type"),
            node_id=kwargs.get("node_id"),
            o_connection=kwargs.get("o_connection"),
            variables=kwargs.get("variables"),
            conversation_uuid=kwargs.get("conversation_uuid"),
        )
    elif event_type == MenuflowNodeEvents.NodeInputData:
        event = NodeInputData(
            event_type=MenuflowEventTypes.NODE,
            event=MenuflowNodeEvents.NodeInputData,
            timestamp=datetime.now(timezone.utc).timestamp(),
            room_id=kwargs.get("room_id"),
            sender=kwargs.get("sender"),
            node_id=kwargs.get("node_id"),
            o_connection=kwargs.get("o_connection"),
            variables=kwargs.get("variables"),
            conversation_uuid=kwargs.get("conversation_uuid"),
        )
    elif event_type == MenuflowNodeEvents.NodeInputTimeout:
        event = NodeInputTimeout(
            event_type=MenuflowEventTypes.NODE,
            event=MenuflowNodeEvents.NodeInputTimeout,
            timestamp=datetime.now(timezone.utc).timestamp(),
            room_id=kwargs.get("room_id"),
            sender=kwargs.get("sender"),
            node_id=kwargs.get("node_id"),
            o_connection=kwargs.get("o_connection"),
            variables=kwargs.get("variables"),
            conversation_uuid=kwargs.get("conversation_uuid"),
        )

    await event.send(config=config)
