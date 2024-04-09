from asyncio import sleep
from typing import Dict

from ..repository import Delay as DelayModel
from ..room import Room
from .base import Base


class Delay(Base):
    def __init__(self, delay_node_data: DelayModel, room: Room, default_variables: Dict) -> None:
        Base.__init__(self, room=room, default_variables=default_variables)
        self.log = self.log.getChild(delay_node_data.get("id"))
        self.content: Dict = delay_node_data

    @property
    def time(self) -> int:
        self.log.debug(f"Waiting {self.content.get('time', 0)} seconds...")
        return self.render_data(data=self.content.get("time", 0))

    @property
    async def o_connection(self) -> str:
        o_connection = await self.get_o_connection()
        return self.render_data(data=o_connection)

    async def run(self):
        self.log.debug(f"Room {self.room.room_id} enters delay node {self.id}")
        await sleep(self.time)
        o_connection = await self.o_connection
        await self.room.update_menu(node_id=o_connection, state=None)
