import json
from queue import LifoQueue
from typing import Dict

from ..db.route import RouteState
from ..repository import Subroutine as SubroutineModel
from ..room import Room
from .base import Base


class Subroutine(Base):
    """This class is used to handle the subroutine node."""

    def __init__(
        self, subroutine_node_data: SubroutineModel, room: Room, default_variables: Dict
    ) -> None:
        Base.__init__(self, room=room, default_variables=default_variables)
        self.log = self.log.getChild(subroutine_node_data.get("id"))
        self.content: Dict = subroutine_node_data

    @property
    def go_sub(self) -> str:
        return self.render_data(self.content.get("go_sub", ""))

    async def run(self):
        """This function runs the subroutine node."""
        self.log.info(f"Room {self.room.room_id} enters subroutine node {self.id}")
        # Get current stack data
        _stack = await self.room.route._stack(room=self.room.id, client=self.room.route.client)
        stack: Dict = json.loads(self.room.route.stack)
        last_node = None

        try:
            go_sub = self.go_sub
            if not go_sub:
                self.log.warning(
                    f"The go_sub value in {self.id} not found. Please check the configuration"
                )
                return

            # If the stack is empty, add the current node to the stack
            if _stack.empty():
                self.log.info(f"Add '{self.id}' node to empty LiFo Stack")
                _stack.put(self.id)
            else:
                # Get the last node from the stack
                last_node = _stack.get(timeout=3)  # seconds

                # If this node is not the last node, add it to the stack
                if last_node and last_node != self.id:
                    self.log.info(f"Add '{self.id}' node to LiFo Stack: {_stack.queue}")
                    _stack.put(self.id)

            # Update the stack in db
            stack[self.room.route.client] = _stack.queue
            self.room.route.stack = json.dumps(stack)
            await self.room.route.update()
        except ValueError as e:
            self.log.warning(e)

        # Update the menu
        if not _stack.empty() and last_node != self.id:
            self.log.debug(f"Go to subroutine: '{self.go_sub}'")
            await self.room.update_menu(node_id=self.go_sub)

        # If the stack is empty, o finished subroutine go to the next node
        o_connection = self.render_data(self.content.get("o_connection", ""))
        if _stack.empty() or last_node == self.id:
            self.log.debug(f"Go to next node: '{o_connection}'")
            await self.room.update_menu(
                node_id=o_connection,
                state=RouteState.END if not o_connection else None,
            )
