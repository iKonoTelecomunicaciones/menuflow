from typing import Dict

from markdown import markdown
from mautrix.types import Format, MessageType, RoomID, TextMessageEventContent

from ..nodes_repository import Message as MessageR
from .base import Base


class Message(Base):
    def __init__(self, message_node_data: MessageR) -> None:
        self.log = self.log.getChild(message_node_data.get("id"))
        self.data: Dict = message_node_data.serialize()

    @property
    def message_type(self) -> MessageType:
        """If the message type is not a text or notice, return a text message type.
        Otherwise, return the message type

        Returns
        -------
            The message type.
        """

        message_type = self.data.get("message_type", "")

        if message_type not in ["m.text", "m.notice"]:
            translated_msg_type = MessageType.TEXT
        else:
            translated_msg_type = MessageType(message_type)

        return translated_msg_type

    @property
    def text(self) -> str:
        return self.render_data(data=self.data.get("text"))

    @property
    def o_connection(self) -> str:
        return self.data.get("o_connection", "")

    async def run(self, room_id: RoomID):

        if not self.text:
            self.log.warning(f"The message {self.id} hasn't been send because the text is empty")
            return

        msg_content = TextMessageEventContent(
            msgtype=self.message_type,
            body=self.text,
            format=Format.HTML,
            formatted_body=markdown(self.text),
        )

        await self.matrix_client.send_message(room_id=room_id, content=msg_content)
