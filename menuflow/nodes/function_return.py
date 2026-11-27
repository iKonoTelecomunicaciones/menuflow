from __future__ import annotations

from ..repository import FunctionReturn as FunctionReturnModel
from ..room import Room
from .base import Base


class FunctionReturn(Base):

    def __init__(
        self, function_return_node_data: FunctionReturnModel, room: Room, default_variables: dict
    ) -> None:
        Base.__init__(self, room=room, default_variables=default_variables)
        self.log = self.log.getChild(function_return_node_data.get("id"))
        self.content: dict = function_return_node_data

    @property
    def value(self):
        return self.render_data(self.content.get("value"))

    async def run(self) -> None:
        self.log.info(f"[{self.room.room_id}] Entering function_return node {self.id}")
        result = self.value
        o_connection = await self.room.fn_return(result=result)

        await self._send_node_event(o_connection=o_connection)
