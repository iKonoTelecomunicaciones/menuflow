from typing import Any

from mautrix.types import MessageEvent

from ..db.route import RouteState
from ..events import MenuflowNodeEvents
from ..events.event_generator import send_node_event
from ..repository import InteractiveInput as InteractiveInputModel
from ..repository import InteractiveMessage
from ..room import Room
from ..utils import Nodes, Util
from .input import Input


class InteractiveInput(Input):
    def __init__(
        self, interactive_input_data: InteractiveInputModel, room: Room, default_variables: dict
    ) -> None:
        Input.__init__(
            self,
            input_node_data=interactive_input_data,
            room=room,
            default_variables=default_variables,
        )
        self.content = interactive_input_data

    @property
    def interactive_message(self) -> dict[str, Any]:
        return self.render_data(self.content.get("interactive_message", {}))

    @property
    def interactive_message_content(self) -> InteractiveMessage:
        interactive_message = InteractiveMessage(
            msgtype="m.interactive_message",
            interactive_message=self.interactive_message,
        )
        interactive_message.trim_reply_fallback()
        return interactive_message

    async def run(self, evt: MessageEvent | None):
        """If the room is in input mode, then set the variable.
        Otherwise, show the message and enter input mode

        Parameters
        ----------
        client : MatrixClient
            The MatrixClient object.
        evt : Optional[MessageEvent]
            The event that triggered the node.

        """

        if self.room.route.state == RouteState.INPUT:
            if not evt or not self.variable:
                self.log.warning(
                    f"[{self.room.room_id}] A problem occurred to trying save the variable"
                )
                await self.room.update_menu(node_id=self.id)
                return

            self.room.set_node_var(content=evt.content.body)
            o_connection = await self.input_text(text=evt.content.body)

            event_type = MenuflowNodeEvents.NodeInputData
            await self.handle_send_event(event_type=event_type, o_connection=o_connection)

        elif self.room.route.state == RouteState.TIMEOUT:
            o_connection = await self.get_case_by_id("timeout")
            event_type = MenuflowNodeEvents.NodeInputTimeout

            await self.room.update_menu(node_id=o_connection, state=None)
            await self.handle_send_event(event_type=event_type, o_connection=o_connection)

        else:
            # This is the case where the room is not in the input state
            # and the node is an input node.
            # In this case, the message is shown and the menu is updated to the node's id
            # and the room state is set to input.
            self.log.debug(f"[{self.room.room_id}] Entering interactive input node {self.id}")
            await self.room.matrix_client.send_message_event(
                room_id=self.room.room_id,
                event_type="m.room.message",
                content=self.interactive_message_content,
            )
            self.room.set_node_var(content="")
            await self.room.update_menu(
                node_id=self.id, state=RouteState.INPUT, update_node_vars=False
            )

            event_type = MenuflowNodeEvents.NodeEntry
            await self.handle_send_event(
                event_type=event_type, o_connection=None, node_type=Nodes.media
            )
