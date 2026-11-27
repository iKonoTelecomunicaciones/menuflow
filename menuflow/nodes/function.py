from __future__ import annotations

from ..repository import Function as FunctionModel
from ..room import Room
from ..utils.function_errors import FunctionFault
from .base import Base


class Function(Base):

    def __init__(
        self, function_node_data: FunctionModel, room: Room, default_variables: dict
    ) -> None:
        Base.__init__(self, room=room, default_variables=default_variables)
        self.log = self.log.getChild(function_node_data.get("id"))
        self.content: dict = function_node_data

    async def run(self) -> None:
        self.log.info(f"[{self.room.room_id}] Entering function node {self.id}")

        frame = self.room.route.current_frame
        if not frame:
            self.log.error(
                f"[{self.room.room_id}] Function node '{self.id}' executed without an active frame"
            )
            raise FunctionFault.not_in_function(
                f"Function node '{self.id}' executed without an active frame"
            )

        if frame.get("function_id") != self.id or not self.room.route.is_running(frame):
            self.log.error(
                f"[{self.room.room_id}] Active frame does not match function '{self.id}'"
            )
            raise FunctionFault.frame_mismatch(self.id)

        o_connection = await self.get_o_connection()
        await self.room.update_menu(node_id=o_connection, state=None)

        await self._send_node_event(o_connection=o_connection)
