from typing import Dict

from markdown import markdown
from mautrix.errors.request import MForbidden
from mautrix.types import Format, MessageType, TextMessageEventContent

from ..db.route import RouteState
from ..events import MenuflowNodeEvents
from ..events.event_generator import send_node_event
from ..repository import Message as MessageModel
from ..room import Room
from ..utils import Nodes
from .base import Base


class Message(Base):
    def __init__(
        self, message_node_data: MessageModel, room: Room, default_variables: Dict
    ) -> None:
        Base.__init__(self, room=room, default_variables=default_variables)
        self.log = self.log.getChild(message_node_data.get("id"))
        self.content: Dict = message_node_data

    @property
    def message_type(self) -> MessageType:
        """If the message type is not a text or notice, return a text message type.
        Otherwise, return the message type

        Returns
        -------
            The message type.
        """

        message_type = self.render_data(self.content.get("message_type", ""))

        if message_type not in ["m.text", "m.notice", "m.image", "m.audio", "m.video", "m.file"]:
            translated_msg_type = MessageType.TEXT
        else:
            translated_msg_type = MessageType(message_type)

        return translated_msg_type

    @property
    def text(self) -> str:
        return self.render_data(data=self.content.get("text", ""))

    @property
    async def o_connection(self) -> str:
        return await self.get_o_connection()

    async def _update_node(self, o_connection: str):
        await self.room.update_menu(
            node_id=o_connection,
            state=RouteState.END if not o_connection else None,
        )

    async def run(self, update_state: bool = True, generate_event: bool = True):
        """This function runs the message node.

        Parameters
        ----------
        update_state : bool
            If true, the state of the room will be updated.
        generate_event : bool
            If true, the event will be generated.
        """
        self.log.debug(f"Room {self.room.room_id} enters message node {self.id}")

        if self.id == RouteState.START.value and self.room.route.state != RouteState.START:
            await self.room.route.clean_up(update_state=False, preserve_constants=True)

        if not self.text:
            self.log.warning(f"The message {self.id} hasn't been send because the text is empty")
        else:
            # Add nl2br extension to markdown to convert new lines to <br> tags
            msg_content = TextMessageEventContent(
                msgtype=self.message_type,
                body=self.text,
                format=Format.HTML,
                formatted_body=markdown(text=self.text, extensions=["nl2br"]),
            )

            try:
                await self.send_message(room_id=self.room.room_id, content=msg_content)
            except MForbidden as e:
                self.log.error(f"Error sending message to {self.room.room_id}. Error: {e}")
                await self._update_node(None)
                return

        o_connection = await self.o_connection
        if update_state:
            await self._update_node(o_connection)

        if generate_event:
            await send_node_event(
                config=self.room.config,
                send_event=self.content.get("send_event"),
                event_type=MenuflowNodeEvents.NodeEntry,
                room_id=self.room.room_id,
                sender=self.room.matrix_client.mxid,
                node_type=Nodes.message,
                node_id=self.id,
                o_connection=o_connection,
                variables=self.room.all_variables | self.default_variables,
            )
