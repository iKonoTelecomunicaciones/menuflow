from __future__ import annotations

from attr import dataclass, ib
from markdown import markdown

from maubot.client import MaubotMatrixClient
from mautrix.types import Format, MessageType, RoomID, SerializableAttrs, TextMessageEventContent

from .user import User
from .utils.base_logger import BaseLogger
from .utils.primitive import OConnection
from .variable import Variable


@dataclass
class Message(SerializableAttrs, BaseLogger):
    id: str = ib(metadata={"json": "id"})
    text: str = ib(metadata={"json": "text"})
    wait: int = ib(default=None, metadata={"json": "wait"})
    o_connection: OConnection = ib(default=None, metadata={"json": "o_connection"})
    variable: str = ib(default=None, metadata={"json": "variable"})

    async def run(
        self, user: User, room_id: RoomID, client: MaubotMatrixClient, i_variable: str = None
    ):
        """It sends a message to the user, and updates the menu

        Parameters
        ----------
        user : User
            The user object
        room_id : RoomID
            The room ID of the room the user is in.
        client : MaubotMatrixClient
            The MaubotMatrixClient object.
        i_variable : str
            The variable that the user has inputted.

        """

        self.log.debug(f"Running message {self.id}")

        if self.variable and i_variable:
            user.set_variable(variable=Variable(self.variable, i_variable))

        if user.state == "SHOW_MESSAGE":
            msg_content = TextMessageEventContent(
                msgtype=MessageType.TEXT,
                body=self.text,
                format=Format.HTML,
                formatted_body=markdown(self.text.format(**user.variable_by_id)),
            )
            await client.send_message(room_id=room_id, content=msg_content)
            await user.update_menu(context=self.o_connection)
