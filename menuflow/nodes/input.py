from __future__ import annotations

from typing import List, Optional

from attr import dataclass, ib
from mautrix.types import MessageEvent

from ..db.room import RoomState
from ..matrix import MatrixClient
from .message import Message
from .switch import Case, Switch


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
        else:
            # This is the case where the room is not in the input state
            # and the node is an input node.
            # In this case, the message is shown and the menu is updated to the node's id
            # and the room state is set to input.
            self.log.debug(f"Room {self.room.room_id} enters input node {self.id}")
            await self.show_message(room_id=self.room.room_id, client=client)
            await self.room.update_menu(node_id=self.id, state=RoomState.INPUT.value)
