from __future__ import annotations

from datetime import datetime
from typing import Dict

from mautrix.types import LocationMessageEventContent, MessageType

from ..db.route import RouteState
from ..events import MenuflowNodeEvents
from ..events.event_generator import send_node_event
from ..repository import Location as LocationModel
from ..room import Room
from .message import Message
from .types import Nodes


class Location(Message):
    def __init__(
        self, location_node_data: LocationModel, room: Room, default_variables: Dict
    ) -> None:
        Message.__init__(self, location_node_data, room=room, default_variables=default_variables)
        self.log = self.log.getChild(location_node_data.get("id"))
        self.content: Dict = location_node_data

    @property
    def longitude(self) -> str:
        return self.render_data(self.content.get("longitude", ""))

    @property
    def latitude(self) -> str:
        return self.render_data(self.content.get("latitude", ""))

    async def run(self):
        location_message = LocationMessageEventContent(
            msgtype=MessageType.LOCATION,
            body=f"User Location geo:{self.longitude},{self.latitude} at {datetime.utcnow()}",
            geo_uri=f"geo:{self.longitude},{self.latitude}",
        )
        await self.send_message(room_id=self.room.room_id, content=location_message)
        await self.room.update_menu(
            node_id=self.o_connection,
            state=RouteState.END if not self.o_connection else None,
        )

        await send_node_event(
            config=self.room.config,
            send_event=self.content.get("send_event"),
            event_type=MenuflowNodeEvents.NodeEntry,
            room_id=self.room.room_id,
            sender=self.room.matrix_client.mxid,
            node_type=Nodes.location,
            node_id=self.id,
            o_connection=self.o_connection,
            variables={**self.room._variables, **self.default_variables},
        )
