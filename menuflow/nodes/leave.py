from typing import Dict

from ..db.room import RoomState
from ..repository import Leave as LeaveModel
from ..room import Room
from .base import Base


class Leave(Base):
    def __init__(self, leave_node_data: LeaveModel, room: Room, default_variables: Dict) -> None:
        Base.__init__(self, room=room, default_variables=default_variables)
        self.log = self.log.getChild(leave_node_data.get("id"))
        self.content: Dict = leave_node_data

    @property
    def reason(self) -> str:
        return self.render_data(data=self.content.get("reason", ""))

    async def run(self):
        self.log.debug(f"Room {self.room.room_id} enters leave node {self.id}")
        await self.room.matrix_client.leave_room(self.room.room_id, self.reason)
        await self.room.update_menu(node_id=None, state=RoomState.END)
