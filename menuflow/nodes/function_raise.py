from __future__ import annotations

from ..repository import FunctionRaise as FunctionRaiseModel
from ..room import Room
from ..utils.types import FunctionErrors
from .base import Base


class FunctionRaise(Base):

    def __init__(
        self, function_raise_node_data: FunctionRaiseModel, room: Room, default_variables: dict
    ) -> None:
        Base.__init__(self, room=room, default_variables=default_variables)
        self.log = self.log.getChild(function_raise_node_data.get("id"))
        self.content: dict = function_raise_node_data

    @property
    def code(self) -> str:
        return self.render_data(self.content.get("code", FunctionErrors.ERROR.value))

    @property
    def message(self) -> str | None:
        return self.render_data(self.content.get("message"))

    @property
    def data(self):
        return self.render_data(self.content.get("data"))

    async def run(self) -> None:
        self.log.info(f"[{self.room.room_id}] Entering function_raise node {self.id}")
        o_connection = await self.room.fn_raise(
            code=self.code, message=self.message, data=self.data
        )
        await self._send_node_event(o_connection=o_connection)
