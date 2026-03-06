import logging
from asyncio import sleep
from typing import Dict

from ..repository import Debug as DebugModel
from ..room import Room
from .base import Base


class Debug(Base):
    def __init__(self, debug_node_data: DebugModel, room: Room, default_variables: Dict) -> None:
        Base.__init__(self, room=room, default_variables=default_variables)
        self.log = self.log.getChild(debug_node_data.get("id"))
        self.content: Dict = debug_node_data

    @property
    def msg(self) -> str:
        return self.render_data(data=self.content.get("msg", ""))

    @property
    def level(self) -> str:
        raw_level = self.render_data(data=self.content.get("level", "debug"))
        normalized = raw_level.strip().upper()
        level = getattr(logging, normalized, None)
        if isinstance(level, int):
            return level

        self.log.warning(
            f"[{self.room.room_id}] Invalid debug level '{raw_level}' in node {self.id}. "
            f"Falling back to DEBUG."
        )
        return logging.DEBUG

    @property
    async def o_connection(self) -> str:
        o_connection = await self.get_o_connection()
        return self.render_data(data=o_connection)

    async def run(self):
        self.log.debug(f"[{self.room.room_id}] Entering debug node {self.id}")

        self.log.log(
            level=self.level, msg=f"[{self.room.room_id}] Debugging msg: {repr(self.msg)}"
        )

        o_connection = await self.o_connection
        await self.room.update_menu(node_id=o_connection, state=None)
