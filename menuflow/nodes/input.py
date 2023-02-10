from __future__ import annotations

import asyncio
from datetime import datetime
from typing import List, Optional

from attr import dataclass, ib
from jinja2 import Template
from mautrix.types import MessageEvent, SerializableAttrs

from ..db.room import RoomState
from ..matrix import MatrixClient
from ..utils.util import Util
from .message import Message
from .switch import Case, Switch


@dataclass
class InactivityOptions(SerializableAttrs):
    chat_timeout: int = ib(default=None, metadata={"json": "chat_timeout"})
    warning_message: str = ib(default=None, metadata={"json": "warning_message"})
    time_between_attempts: int = ib(default=None, metadata={"json": "time_between_attempts"})
    attempts: int = ib(default=None, metadata={"json": "attempts"})


@dataclass
class Input(Switch, Message):
    """
    ## Input

    An input type node allows sending a message formatted with jinja variables
    and capturing the response to transit to another node according to the validation.

    content:

    ```
    - id: i1
      type: input
      text: 'Enter a number'
      variable: opt
      validation: '{{ opt.isdigit() }}'
      cases:
      - id: true
        o_connection: m1
      - id: false
        o_connection: m2
      - id: default
        o_connection: m3
    ```
    """

    variable: str = ib(default=None, metadata={"json": "variable"})
    cases: List[Case] = ib(metadata={"json": "cases"}, factory=list)
    inactivity_options: InactivityOptions = ib(
        default=None, metadata={"json": "inactivity_options"}
    )

    @property
    def _inactivity_message(self) -> Template:
        return self.render_data(self.inactivity_options.warning_message)

    @property
    def _closing_message(self) -> Template:
        return self.render_data(self.inactivity_options.closing_message)

    async def run(self, client: MatrixClient, evt: Optional[MessageEvent]):
        """If the room is in input mode, then set the variable.
        Otherwise, show the message and enter input mode

        Parameters
        ----------
        client : MatrixClient
            The MatrixClient object.
        evt : Optional[MessageEvent]
            The event that triggered the node.

        """

        if self.room.state == RoomState.INPUT.value:
            if not evt:
                self.log.warning("The [evt] is empty")
                return

            self.log.debug(f"Creating [variable: {self.variable}] [content: {evt.content.body}]")
            try:
                await self.room.set_variable(
                    self.variable,
                    int(evt.content.body) if evt.content.body.isdigit() else evt.content.body,
                )
            except ValueError as e:
                self.log.warning(e)

            # If the node has an output connection, then update the menu to the output connection.
            # Otherwise, run the node and update the menu to the output connection.
            await self.room.update_menu(node_id=self.o_connection or await super().run())
            if self.inactivity_options:
                await Util.cancel_inactivity_task(room_id=self.room.room_id)
        else:
            # This is the case where the room is not in the input state
            # and the node is an input node.
            # In this case, the message is shown and the menu is updated to the node's id
            # and the room state is set to input.
            self.log.debug(f"Room {self.room.room_id} enters input node {self.id}")
            await self.show_message(client=client)
            await self.room.update_menu(node_id=self.id, state=RoomState.INPUT.value)
            if self.inactivity_options:
                await self.inactivity_task(client=client)

    async def inactivity_task(self, client: MatrixClient):
        """It spawns a task to harass the client to enter information to input option

        Parameters
        ----------
        client : MatrixClient
            The MatrixClient object

        """

        self.log.debug(f"Inactivity loop starts in room: {self.room.room_id}")
        asyncio.create_task(self.timeout_active_chats(client=client), name=self.room.room_id)

    async def timeout_active_chats(self, client: MatrixClient):
        """It sends messages in time intervals to communicate customer
        that not entered information to input option.

        Parameters
        ----------
        client : MatrixClient
            The Matrix client object.

        """

        try:
            # wait the given time to start the task
            await asyncio.sleep(self.inactivity_options.chat_timeout)
        except Exception as e:
            self.log.debug(f"{e}")

        count = 0
        while True:
            self.log.debug(f"Inactivity loop: {datetime.now()} -> {self.room.room_id}")
            if self.inactivity_options.attempts == count:
                self.log.debug(f"INACTIVITY TRIES COMPLETED -> {self.room.room_id}")
                o_connection = await self.get_case_by_id("timeout")
                await self.room.update_menu(node_id=o_connection, state=None)
                await client.algorithm(room=self.room)
                break

            try:
                await self.show_message(client=client, message=self._inactivity_message)
            except Exception as e:
                self.log.debug(e)

            await asyncio.sleep(self.inactivity_options.time_between_attempts)
            count += 1
