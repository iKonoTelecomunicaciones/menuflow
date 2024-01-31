from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from mautrix.types import (
    LocationMessageEventContent,
    MediaMessageEventContent,
    MessageEvent,
    MessageEventContent,
    MessageType,
)

from ..db.route import RouteState
from ..events import MenuflowNodeEvents
from ..events.event_generator import send_node_event
from ..repository import Input as InputModel
from ..room import Room
from ..utils import Nodes, Util
from .message import Message
from .switch import Switch

if TYPE_CHECKING:
    from ..middlewares import IRMMiddleware


class Input(Switch, Message):
    def __init__(self, input_node_data: InputModel, room: Room, default_variables: Dict) -> None:
        Switch.__init__(self, input_node_data, room=room, default_variables=default_variables)
        Message.__init__(self, input_node_data, room=room, default_variables=default_variables)
        self.content = input_node_data
        self.middleware: Optional[IRMMiddleware] = None

    @property
    def variable(self) -> str:
        return self.render_data(self.content.get("variable", ""))

    @property
    def input_type(self) -> MessageType:
        return MessageType(self.render_data(self.content.get("input_type", "m.text")))

    @property
    def inactivity_options(self) -> Dict[str, Any]:
        data: Dict = self.content.get("inactivity_options", {})
        self.chat_timeout: int = data.get("chat_timeout", 0)
        self.warning_message: str = self.render_data(data.get("warning_message", ""))
        self.time_between_attempts: int = data.get("time_between_attempts", 0)
        self.attempts: int = data.get("attempts", 0)

        return data

    async def _set_input_content(
        self, content: MediaMessageEventContent | LocationMessageEventContent
    ) -> str:
        if self.input_type == content.msgtype:
            input_content = (
                content.serialize()
                if isinstance(content, MediaMessageEventContent)
                else content.geo_uri
            )
            await self.room.set_variable(self.variable, input_content)
            return await self.get_case_by_id(True)
        else:
            return await self.get_case_by_id(False)

    async def input_media(self, content: MediaMessageEventContent):
        o_connection = await self._set_input_content(content)
        await self.room.update_menu(o_connection or "default")
        return o_connection

    async def input_location(self, content: LocationMessageEventContent):
        o_connection = await self._set_input_content(content)
        await self.room.update_menu(o_connection or "default")
        return o_connection

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
        return await Switch.run(self, generate_event=False)

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

        if self.room.route.state == RouteState.INPUT:
            if not evt:
                self.log.warning("A problem occurred getting message event.")
                return

            if self.input_type == MessageType.TEXT:
                o_connection = await self.input_text(content=evt.content)
            elif self.input_type in [
                MessageType.AUDIO,
                MessageType.IMAGE,
                MessageType.FILE,
                MessageType.VIDEO,
            ]:
                if self.input_type == MessageType.IMAGE and self.middleware:
                    await self.middleware.run(
                        image_mxc=evt.content.url,
                        content_type=evt.content.info.mimetype,
                        filename=evt.content.body,
                    )
                    o_connection = await Switch.run(self, generate_event=False)
                else:
                    o_connection = await self.input_media(content=evt.content)
            elif self.input_type == MessageType.LOCATION:
                o_connection = await self.input_location(content=evt.content)

            if self.inactivity_options:
                await Util.cancel_task(task_name=self.room.room_id)

            await send_node_event(
                config=self.room.config,
                send_event=self.content.get("send_event"),
                event_type=MenuflowNodeEvents.NodeInputData,
                room_id=self.room.room_id,
                sender=self.room.matrix_client.mxid,
                node_id=self.id,
                o_connection=o_connection,
                variables=self.room.all_variables | self.default_variables,
            )
        else:
            # This is the case where the room is not in the input state
            # and the node is an input node.
            # In this case, the message is shown and the menu is updated to the node's id
            # and the room state is set to input.
            self.log.debug(f"Room {self.room.room_id} enters input node {self.id}")
            await Message.run(self, update_state=False, generate_event=False)
            await self.room.update_menu(node_id=self.id, state=RouteState.INPUT)
            if self.inactivity_options:
                await self.inactivity_task()

            await send_node_event(
                config=self.room.config,
                send_event=self.content.get("send_event"),
                event_type=MenuflowNodeEvents.NodeEntry,
                room_id=self.room.room_id,
                sender=self.room.matrix_client.mxid,
                node_type=Nodes.input,
                node_id=self.id,
                o_connection=None,
                variables=self.room.all_variables | self.default_variables,
            )

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

                await send_node_event(
                    config=self.room.config,
                    send_event=self.content.get("send_event"),
                    event_type=MenuflowNodeEvents.NodeInputTimeout,
                    room_id=self.room.room_id,
                    sender=self.room.matrix_client.mxid,
                    node_id=self.id,
                    o_connection=o_connection,
                    variables=self.room.all_variables | self.default_variables,
                )

                await self.room.matrix_client.algorithm(room=self.room)
                break

            await self.room.matrix_client.send_text(
                room_id=self.room.room_id, text=self.warning_message
            )
            await asyncio.sleep(self.time_between_attempts)
            count += 1
