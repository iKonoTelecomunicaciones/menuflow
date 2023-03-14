from typing import Dict

from markdown import markdown
from mautrix.types import Format, MessageType, TextMessageEventContent

from ..db.room import RoomState
from ..repository import Message as MessageModel
from .base import Base


class Message(Base):
    def __init__(self, message_node_data: MessageModel) -> None:
        self.log = self.log.getChild(message_node_data.get("id"))
        self.data: Dict = message_node_data

    @property
    def message_type(self) -> MessageType:
        """If the message type is not a text or notice, return a text message type.
        Otherwise, return the message type

        Returns
        -------
            The message type.
        """

        message_type = self.data.get("message_type", "")

        if message_type not in ["m.text", "m.notice", "m.image", "m.audio", "m.video", "m.file"]:
            translated_msg_type = MessageType.TEXT
        else:
            translated_msg_type = MessageType(message_type)

        return translated_msg_type

    @property
    def text(self) -> str:
        return self.render_data(data=self.data.get("text", ""))

    @property
    def o_connection(self) -> str:
        return self.data.get("o_connection", "")

    async def run(self):
        self.log.debug(f"Room {self.room.room_id} enters message node {self.id}")

        if not self.text:
            self.log.warning(f"The message {self.id} hasn't been send because the text is empty")
            return

        msg_content = TextMessageEventContent(
            msgtype=self.message_type,
            body=self.text,
            format=Format.HTML,
            formatted_body=markdown(self.text),
        )

        await self.matrix_client.send_message(room_id=self.room.room_id, content=msg_content)

        await self.room.update_menu(
            node_id=self.o_connection,
            state=RoomState.END if not self.o_connection else None,
        )
