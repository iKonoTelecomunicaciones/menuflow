from typing import Any, Dict

from markdown import markdown
from mautrix.types import Format, MessageType, TextMessageEventContent

from ..db.room import RoomState
from ..events import MenuflowNodeEvents
from ..events.event_generator import send_node_event
from ..repository import Message as MessageModel
from ..room import Room
from .base import Base
from .types import Nodes


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
    def o_connection(self) -> str:
        return self.render_data(self.content.get("o_connection", ""))

    async def _update_node(self):
        await self.room.update_menu(
            node_id=self.o_connection,
            state=RoomState.END if not self.o_connection else None,
        )

    async def run(self, generate_event: bool = True):
        self.log.debug(f"Room {self.room.room_id} enters message node {self.id}")

        if not self.text:
            self.log.warning(f"The message {self.id} hasn't been send because the text is empty")
        else:
            msg_content = TextMessageEventContent(
                msgtype=self.message_type,
                body=self.text,
                format=Format.HTML,
                formatted_body=markdown(self.text),
            )

            await self.send_message(room_id=self.room.room_id, content=msg_content)

        await self._update_node()

        if generate_event:
            await send_node_event(
                config=self.room.config,
                send_event=self.content.get("send_event"),
                event_type=MenuflowNodeEvents.NodeEntry,
                room_id=self.room.room_id,
                sender=self.room.matrix_client.mxid,
                node_type=Nodes.message,
                node_id=self.id,
                o_connection=self.o_connection,
                variables={**self.room._variables, **self.default_variables},
            )
