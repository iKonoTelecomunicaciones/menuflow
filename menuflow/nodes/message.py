from __future__ import annotations

from asyncio import sleep

from attr import dataclass, ib
from jinja2 import Template
from markdown import markdown
from mautrix.errors.request import MLimitExceeded
from mautrix.types import Format, MessageType, RoomID, TextMessageEventContent

from ..matrix import MatrixClient
from ..user import User
from .node import Node


@dataclass
class Message(Node):
    """
    ## Message

    A message node allows a message to be sent,
    these messages can be formatted using jinja variables.

    content:

    ```
    - id: m1
      type: message
      text: "Hello World!"
      o_connection: m2
    ```
    """

    text: str = ib(default=None, metadata={"json": "text"})
    o_connection: str = ib(default=None, metadata={"json": "o_connection"})

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
        if not self.text:
            return

        msg_content = TextMessageEventContent(
            msgtype=MessageType.TEXT,
            body=self.text,
            format=Format.HTML,
            formatted_body=markdown(self.template.render(**user._variables)),
        )

        # A way to handle the error that is thrown when the bot sends too many messages too quickly.
        try:
            await client.send_message(room_id=room_id, content=msg_content)
        except MLimitExceeded as e:
            self.log.warn(e)
            await sleep(5)
            await client.send_message(room_id=room_id, content=msg_content)
