from __future__ import annotations

from datetime import datetime
from typing import Dict

from mautrix.types import LocationMessageEventContent, MessageType

from ..db.room import RoomState
from ..repository import Location as LocationModel
from .message import Message


class Location(Message):
    def __init__(self, location_node_data: LocationModel) -> None:
        Message.__init__(self, location_node_data)
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
            state=RoomState.END if not self.o_connection else None,
        )
