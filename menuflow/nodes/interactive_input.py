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
                self.log.warning("A problem occurred to trying save the variable")
                await self.room.update_menu(node_id=self.id)
                return

            o_connection = await self.input_text(text=evt.content.body)

            if self.inactivity_options:
                await Util.cancel_task(task_name=self.room.room_id)

            await send_node_event(
                config=self.room.config,
                send_event=self.content.get("send_event"),
                event_type=MenuflowNodeEvents.NodeInputData,
                room_id=self.room.room_id,
                sender=self.room.matrix_client.mxid,
                node_id=self.id,
                o_connection=o_connection,
                variables=self.room.all_variables | self.default_variables,
            )
        else:
            # This is the case where the room is not in the input state
            # and the node is an input node.
            # In this case, the message is shown and the menu is updated to the node's id
            # and the room state is set to input.
            self.log.debug(f"Room {self.room.room_id} enters input node {self.id}")
            await self.room.matrix_client.send_message_event(
                room_id=self.room.room_id,
                event_type="m.room.message",
                content=self.interactive_message_content,
            )
            await self.room.update_menu(node_id=self.id, state=RouteState.INPUT)
            if self.inactivity_options:
                await self.inactivity_task()

            await send_node_event(
                config=self.room.config,
                send_event=self.content.get("send_event"),
                event_type=MenuflowNodeEvents.NodeEntry,
                room_id=self.room.room_id,
                sender=self.room.matrix_client.mxid,
                node_type=Nodes.media,
                node_id=self.id,
                o_connection=None,
                variables=self.room.all_variables | self.default_variables,
            )
