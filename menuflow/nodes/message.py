from __future__ import annotations

from asyncio import sleep
from typing import Optional

from attr import dataclass, ib
from jinja2 import Template
from markdown import markdown
from mautrix.errors.request import MLimitExceeded
from mautrix.types import Format, MessageType, RoomID, TextMessageEventContent

from ..matrix import MatrixClient
from .flow_object import FlowObject


@dataclass
class Message(FlowObject):
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

    text: str = ib(default=None)
    o_connection: str = ib(default=None)

    @property
    def _text(self) -> Template:
        return self.render_data(self.text)

    async def run(self) -> str:
        pass

    async def show_message(self, client: MatrixClient, message: Optional[str] = None):
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
            self.log.warning(f"The message {self.id} hasn't been send because the text is empty")
            return

        msg_content = TextMessageEventContent(
            msgtype=MessageType.TEXT,
            body=message or self.text,
            format=Format.HTML,
            formatted_body=markdown(message or self._text),
        )

        # A way to handle the error that is thrown when the bot sends too many messages too quickly.
        try:
            await client.send_message(room_id=self.room.room_id, content=msg_content)
        except MLimitExceeded as e:
            self.log.warn(e)
            await sleep(5)
            await client.send_message(room_id=self.room.room_id, content=msg_content)
