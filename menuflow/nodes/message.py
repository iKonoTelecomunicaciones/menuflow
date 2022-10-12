from __future__ import annotations

from attr import dataclass, ib
from jinja2 import Template
from markdown import markdown
from mautrix.types import Format, MessageType, RoomID, TextMessageEventContent

from ..matrix import MatrixClient
from ..user import User
from .node import Node


@dataclass
class Message(Node):

    text: str = ib(default=None, metadata={"json": "text"})
    o_connection: str = ib(default=None, metadata={"json": "o_connection"})
    variable: str = ib(default=None, metadata={"json": "variable"})

    @property
    def template(self) -> Template:
        return Template(self.text)

    async def show_message(self, user: User, room_id: RoomID, client: MatrixClient):
        """It takes a dictionary of variables, a room ID, and a client,
        and sends a message to the room with the template rendered with the variables

        Parameters
        ----------
        variables : dict
            A dictionary of variables to pass to the template.
        room_id : RoomID
            The room ID to send the message to.
        client : MatrixClient
            The MatrixClient instance that is running the plugin.

        """

        msg_content = TextMessageEventContent(
            msgtype=MessageType.TEXT,
            body=self.text,
            format=Format.HTML,
            formatted_body=markdown(self.template.render(**user._variables)),
        )
        await client.send_message(room_id=room_id, content=msg_content)
