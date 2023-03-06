from __future__ import annotations

import json
from logging import getLogger
from typing import Any, Dict, Optional, cast

from mautrix.client import Client as MatrixClient
from mautrix.types import MessageEvent, RoomID
from mautrix.util.logging import TraceLogger

from .config import Config
from .db.room import Room as DBRoom
from .db.room import RoomState
from .flow import Flow
from .nodes import CheckTime, HTTPRequest, Input, Message, Switch

AVAILABLE_NODES = (Message, Input, Switch, CheckTime, HTTPRequest)


class Room(DBRoom):
    by_room_id: Dict[RoomID, "Room"] = {}

    config: Config
    log: TraceLogger = getLogger("menuflow.room")
    matrix_client: MatrixClient

    node: Message | Input | Switch | CheckTime | HTTPRequest = None
    room_id: RoomID
    menuflow: Flow

    def __init__(
        self,
        room_id: RoomID,
        node_id: str,
        state: RoomState = None,
        id: int = None,
        variables: str = "{}",
    ) -> None:
        self._variables: Dict = json.loads(variables)
        super().__init__(
            id=id, room_id=room_id, node_id=node_id, state=state, variables=f"{variables}"
        )
        self.log = self.log.getChild(self.room_id)

    def _add_to_cache(self) -> None:
        if self.room_id:
            self.by_room_id[self.room_id] = self

    async def execute_current_node(self, input_event: Optional[MessageEvent] = None) -> Any:
        """It executes the current node and returns the result

        Parameters
        ----------
        input_event : Optional[MessageEvent]
            The message event that triggered the flow.

        Returns
        -------
            The return value of the node.run() method.

        """
        self.log.debug(f"$$$$$$$$$ {self.node=}")
        self.log.debug(f"Executing node [{self.node.type}][{self.node.id}] ...")

        if isinstance(self.node, (Input, Message)):
            self.node.client = self.matrix_client
            if isinstance(self.node, Input):
                return await self.node.run(input_event=input_event)

            self.log.debug(f"1######")
            if self.node.o_connection:
                next_node = self.menuflow.get_node_by_id(self.node.o_connection)
                await self.update_menu(next_node)
            else:
                await self.update_menu(node=None, state=RoomState.END)

            self.log.debug(f"2######")
            return await self.node.run(room_id=self.room_id, variables=self._variables)

        elif isinstance(self.node, CheckTime):
            return await self.node.run()

        elif isinstance(self.node, (HTTPRequest, Switch)):
            if isinstance(self.node, HTTPRequest):
                return await self.update_menu(
                    await self.node.run(session=self.matrix_client.api.session)
                )

            return await self.update_menu(await self.node.run())

    async def clean_up(self):
        """It deletes the room from the `by_room_id` dictionary, resets the variables,
        resets the node id, and updates the room state
        """
        del self.by_room_id[self.room_id]
        self.variables = "{}"
        self._variables = {}
        self.state = None
        message = Message(id="start", type="message", text="Hello world!")
        await self.update_menu(node=message)

    async def set_variable(self, variable_id: str, value: Any):
        """It saves a variable to the database

        Parameters
        ----------
        variable_id : str
            The name of the variable you want to save.
        value : Any
            The value of the variable.

        """
        self._variables[variable_id] = value
        self.variables = json.dumps(self._variables)
        self.log.debug(
            f"Saving variable [{variable_id}] to room [{self.room_id}] :: content [{value}]"
        )
        await self.update()

    async def set_variables(self, variables: Dict):
        """It takes a dictionary of variable IDs and values, and sets the variables to the values

        Parameters
        ----------
        variables : Dict
            A dictionary of variable names and values.

        """
        for variable in variables:
            await self.set_variable(variable_id=variable, value=variables[variable])

    async def update_menu(
        self, node: Message | Input | Switch | CheckTime | HTTPRequest, state: RoomState = None
    ):
        """This function updates the menu of the room by setting the node and state of the room

        Parameters
        ----------
        node : Message | Input | Switch | CheckTime | HTTPRequest
            The node that the room will be updated to.
        state : RoomState
            The state of the room.

        """

        self.log.debug(
            f"The [room: {self.room_id}] will update his [node: {self.node_id}] to [{node.id}] "
            f"and his [state: {self.state}] to [{state}]"
        )

        await self.set_node(node=node)

        if state:
            await self.set_state(state=state)

        self._add_to_cache()

    async def set_node(self, node: Message | Input | Switch | CheckTime | HTTPRequest):
        """It sets the node that this node is connected to

        Parameters
        ----------
        node : Message | Input | Switch | CheckTime | HTTPRequest
            The node that the connection is connected to.

        """
        self.node_id = node.id
        self.node = node

        await self.update()

    async def set_state(self, state: RoomState):
        """It sets the state of the room to the state passed in, and then updates the room

        Parameters
        ----------
        state : RoomState
            The state of the room.

        """
        self.state = state

        await self.update()

    async def get_variable(self, variable_id: str) -> Any | None:
        """This function returns the value of a variable with the given ID

        Parameters
        ----------
        variable_id : str
            The id of the variable you want to get.

        Returns
        -------
            The value of the variable with the given id.

        """
        return self._variables.get(variable_id)

    async def get_current_node(self) -> Message | Input | Switch | CheckTime | HTTPRequest:
        """It returns the current node.

        Returns
        -------
            The node that is currently being used.

        """
        return await self.menuflow.get_node_by_id(node_id=self.node_id)

    @classmethod
    async def get_by_room_id(
        cls, room_id: RoomID, menuflow: Flow, create: bool = True
    ) -> "Room" | None:
        """It gets a room from the database, or creates one if it doesn't exist

        Parameters
        ----------
        room_id : RoomID
            The room's ID.
        create : bool, optional
            If True, the room will be created if it doesn't exist.

        Returns
        -------
            The room object

        """
        try:
            return cls.by_room_id[room_id]
        except KeyError:
            pass

        room = cast(cls, await super().get_by_room_id(room_id))

        if room is not None:
            room.menuflow = menuflow
            room.node = room.menuflow.get_node_by_id(room.node_id)
            room._add_to_cache()
            return room

        if create:
            room = cls(room_id=room_id, node_id=RoomState.START.value)
            await room.insert()
            room = cast(cls, await super().get_by_room_id(room_id))
            room.menuflow = menuflow
            room.node = room.menuflow.get_node_by_id(room.node_id)
            room._add_to_cache()
            return room
