from __future__ import annotations

from email import message

from attr import dataclass, ib
from markdown import markdown

from maubot.client import MaubotMatrixClient
from mautrix.types import Format, MessageType, RoomID, SerializableAttrs, TextMessageEventContent

from .user import User
from .utils.base_logger import BaseLogger
from .utils.primitive import OConnection


@dataclass
class Message(SerializableAttrs, BaseLogger):
    id: str = ib(metadata={"json": "id"})
    text: str = ib(metadata={"json": "text"})
    wait: int = ib(default=None, metadata={"json": "wait"})
    o_connection: OConnection = ib(default=None, metadata={"json": "o_connection"})
    variable: str = ib(default=None, metadata={"json": "variable"})

    async def show_message(self, user: User, room_id: RoomID, client: MaubotMatrixClient):
        """It sends a message to the user

        Parameters
        ----------
        user : User
            The user that triggered the event.
        room_id : RoomID
            The room ID to send the message to.
        client : MaubotMatrixClient
            The MaubotMatrixClient instance that is used to send the message.

        """
        msg_content = TextMessageEventContent(
            msgtype=MessageType.TEXT,
            body=self.text,
            format=Format.HTML,
            formatted_body=markdown(self.text.format(**user.variables_data)),
        )
        await client.send_message(room_id=room_id, content=msg_content)
