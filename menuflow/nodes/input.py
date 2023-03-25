import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from mautrix.types import MessageEvent, MessageEventContent, MessageType

from ..db.room import RoomState
from ..repository import Input as InputModel
from ..utils import Util
from .message import Message
from .switch import Switch


class Input(Switch, Message):
    def __init__(self, input_node_data: InputModel) -> None:
        Switch.__init__(self, input_node_data)
        Message.__init__(self, input_node_data)
        self.data = input_node_data

    @property
    def variable(self) -> str:
        return self.render_data(self.data.get("variable", ""))

    @property
    def input_type(self) -> MessageType:
        return MessageType(self.render_data(self.data.get("input_type", "m.text")))

    @property
    def inactivity_options(self) -> Dict[str, Any]:
        data: Dict = self.data.get("inactivity_options", {})
        self.chat_timeout: int = data.get("chat_timeout", 0)
        self.warning_message: str = self.render_data(data.get("warning_message", ""))
        self.time_between_attempts: int = data.get("time_between_attempts", 0)
        self.attempts: int = data.get("attempts", 0)

        return data

    async def input_media(self, content: MessageEventContent):
        """It checks if the input type is the same as the message type, if it is,
        it sets the variable to the message content and goes to the next case, if it isn't,
        it goes to the previous case

        Parameters
        ----------
        content : MessageEventContent
            MessageEventContent

        """
        if self.input_type != content.msgtype:
            o_connection = await self.get_case_by_id(False)
        else:
            await self.room.set_variable(self.variable, content.serialize())
            o_connection = await self.get_case_by_id(True)

        await self.room.update_menu(o_connection or "default")

    async def input_text(self, content: MessageEventContent):
        """It takes the input from the user and sets the variable to the input

        Parameters
        ----------
        content : MessageEventContent
            The content of the message event.

        """
        try:
            await self.room.set_variable(
                self.variable,
                int(content.body) if content.body.isdigit() else content.body,
            )
        except ValueError as e:
            self.log.warning(e)

        # If the node has an output connection, then update the menu to the output connection.
        # Otherwise, run the node and update the menu to the output connection.
        await Switch.run(self)

    async def run(self, evt: Optional[MessageEvent]):
        """If the room is in input mode, then set the variable.
        Otherwise, show the message and enter input mode

        Parameters
        ----------
        client : MatrixClient
            The MatrixClient object.
        evt : Optional[MessageEvent]
            The event that triggered the node.

        """

        if self.room.state == RoomState.INPUT:
            if not evt or not self.variable:
                self.log.warning("A problem occurred to trying save the variable")
                return

            if self.input_type == MessageType.TEXT:
                await self.input_text(content=evt.content)
            elif self.input_type in [
                MessageType.AUDIO,
                MessageType.IMAGE,
                MessageType.FILE,
                MessageType.VIDEO,
            ]:
                await self.input_media(content=evt.content)

            if self.inactivity_options:
                await Util.cancel_task(task_name=self.room.room_id)
        else:
            # This is the case where the room is not in the input state
            # and the node is an input node.
            # In this case, the message is shown and the menu is updated to the node's id
            # and the room state is set to input.
            self.log.debug(f"Room {self.room.room_id} enters input node {self.id}")
            await Message.run(self)
            await self.room.update_menu(node_id=self.id, state=RoomState.INPUT)
            if self.inactivity_options:
                await self.inactivity_task()

    async def inactivity_task(self):
        """It spawns a task to harass the client to enter information to input option

        Parameters
        ----------
        client : MatrixClient
            The MatrixClient object

        """

        self.log.debug(f"Inactivity loop starts in room: {self.room.room_id}")
        asyncio.create_task(self.timeout_active_chats(), name=self.room.room_id)

    async def timeout_active_chats(self):
        """It sends messages in time intervals to communicate customer
        that not entered information to input option.

        Parameters
        ----------
        client : MatrixClient
            The Matrix client object.

        """

        # wait the given time to start the task
        await asyncio.sleep(self.chat_timeout)

        count = 0
        while True:
            self.log.debug(f"Inactivity loop: {datetime.now()} -> {self.room.room_id}")
            if self.attempts == count:
                self.log.debug(f"INACTIVITY TRIES COMPLETED -> {self.room.room_id}")
                o_connection = await self.get_case_by_id("timeout")
                await self.room.update_menu(node_id=o_connection, state=None)
                await self.matrix_client.algorithm(room=self.room)
                break

            await self.matrix_client.send_text(
                room_id=self.room.room_id, text=self.warning_message
            )
            await asyncio.sleep(self.time_between_attempts)
            count += 1
