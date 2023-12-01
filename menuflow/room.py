from __future__ import annotations

import json
from asyncio import Future, Lock
from collections import defaultdict
from logging import getLogger
from typing import Any, Dict, cast

from mautrix.client import Client as MatrixClient
from mautrix.types import EventType, RoomID, StateEventContent
from mautrix.util.async_getter_lock import async_getter_lock
from mautrix.util.logging import TraceLogger

from .config import Config
from .db.room import Room as DBRoom
from .db.room import RoomState
from .utils import Util


class Room(DBRoom):
    by_room_id: Dict[RoomID, "Room"] = {}
    pending_invites: Dict[RoomID, Future] = {}
    _async_get_locks: dict[Any, Lock] = defaultdict(lambda: Lock())

    config: Config
    log: TraceLogger = getLogger("menuflow.room")

    matrix_client: MatrixClient

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

    async def clean_up(self):
        self.log.info(f"Cleaning up room {self.room_id}")
        await Util.cancel_task(task_name=self.room_id)
        del self.by_room_id[self.room_id]
        self.variables = "{}"
        self._variables = {}
        self.node_id = RoomState.START.value
        self.state = None
        await self.update()

    @property
    async def creator(self) -> Dict:
        """This function retrieves the creator of a Matrix room.

        Returns
        -------
            The `creator` of the Matrix room is being returned as a string.

        """
        created_room_event: StateEventContent = await self.matrix_client.get_state_event(
            self.room_id, event_type=EventType.ROOM_CREATE
        )
        return created_room_event.get("creator")

    @classmethod
    @async_getter_lock
    async def get_by_room_id(cls, room_id: RoomID, create: bool = True) -> "Room" | None:
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
            room._add_to_cache()
            return room

        if create:
            room = cls(room_id=room_id, node_id=RoomState.START.value)
            await room.insert()
            room = cast(cls, await super().get_by_room_id(room_id))
            room._add_to_cache()
            return room

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

    async def set_variable(self, variable_id: str, value: Any):
        if not variable_id:
            return

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

    async def update_menu(self, node_id: str | RoomState, state: RoomState = None):
        """Updates the menu's node_id and state, and then updates the menu's content

        Parameters
        ----------
        node_id : str
            The node_id of the menu. This is used to determine which menu to display.
        state : str
            The state of the menu. This is used to determine which menu to display.

        """
        self.log.debug(
            f"The [room: {self.room_id}] will update his [node: {self.node_id}] to [{node_id.value if isinstance(node_id, RoomState) else node_id}] "
            f"and his [state: {self.state}] to [{state}]"
        )
        self.node_id = node_id.value if isinstance(node_id, RoomState) else node_id
        self.state = state
        await self.update()
        self._add_to_cache()
