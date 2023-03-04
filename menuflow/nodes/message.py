from __future__ import annotations

from asyncio import sleep
from typing import Optional

from attr import dataclass, ib
from jinja2 import Template
from markdown import markdown
from mautrix.errors.request import MLimitExceeded
from mautrix.types import Format, MessageType, TextMessageEventContent

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
    client: MatrixClient

    @property
    def _text(self) -> Template:
        return self.render_data(self.text)

    async def send_message(self, message: str):
        """It sends a message to the room.

        Parameters
        ----------
        message : str
            The message to send.

        """

        msg_content = TextMessageEventContent(
            msgtype=MessageType.TEXT,
            body=message,
            format=Format.HTML,
            formatted_body=markdown(message),
        )

        # A way to handle the error that is thrown when the bot sends too many messages too quickly.
        try:
            await self.client.send_message(room_id=self.room.room_id, content=msg_content)
        except MLimitExceeded as e:
            self.log.warn(e)
            await sleep(5)
            await self.client.send_message(room_id=self.room.room_id, content=msg_content)

    async def run(self):
        """It sends a message to the channel

        Returns
        -------
            The message object

        """
        if not self.text:
            self.log.warning(f"The message {self.id} hasn't been send because the text is empty")
            return

        await self.send_message(message=self._text)
