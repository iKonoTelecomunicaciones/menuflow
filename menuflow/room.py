from __future__ import annotations

import json
from logging import getLogger
from typing import Any, Dict, Optional, cast

from mautrix.client import Client as MatrixClient
from mautrix.types import EventType, RoomID, StateEventContent, UserID
from mautrix.util.logging import TraceLogger

from .config import Config
from .db.room import Room as DBRoom
from .db.route import Route, RouteState
from .utils import Util


class Room(DBRoom):
    by_room_id: Dict[RoomID, "Room"] = {}

    config: Config
    log: TraceLogger = getLogger("menuflow.room")

    matrix_client: MatrixClient

    def __init__(
        self,
        room_id: RoomID,
        id: int = None,
        variables: str = "{}",
    ) -> None:
        self._variables: Dict = json.loads(variables)
        super().__init__(id=id, room_id=room_id, variables=f"{variables}")
        self.log = self.log.getChild(self.room_id)
        self.route: Route = None

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

    @property
    def all_variables(self) -> Dict:
        return self._variables | self.route._variables

    @classmethod
    async def get_by_room_id(
        cls, room_id: RoomID, bot_id: UserID, create: bool = True
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
            room = cls.by_room_id[room_id]
            route = await Route.get_by_room_and_client(room=room.id, client=bot_id)
            room.route = route
            return room
        except KeyError:
            pass

        room = cast(cls, await super().get_by_room_id(room_id))

        if room is not None:
            route = await Route.get_by_room_and_client(room=room.id, client=bot_id)
            room.route = route
            room._add_to_cache()
            return room

        if create:
            room = cls(room_id=room_id, node_id="start")
            await room.insert()
            room = cast(cls, await super().get_by_room_id(room_id))
            route = await Route.get_by_room_and_client(room=room.id, client=bot_id)
            room.route = route
            room._add_to_cache()
            return room

    def _add_to_cache(self) -> None:
        if self.room_id:
            self.by_room_id[self.room_id] = self

    async def clean_up(self):
        await Util.cancel_task(task_name=self.room_id)
        del self.by_room_id[self.room_id]
        await self.route.clean_up()
        self.route = None
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
        return self.all_variables.get(variable_id)

    async def set_variable(self, variable_id: str, value: Any) -> None:
        """The function sets a variable value in either the room or route scope
        and updates the corresponding JSON data.

        Parameters
        ----------
        variable_id : str
            The `variable_id` parameter is a string that represents the identifier of the variable you want to set.
            It can be in the format "scope.key" or just "key".
            The "scope" indicates the scope of the variable (e.g., "room" or "route")."
        value : Any
            The `value` parameter in the `set_variable` function
            is the value that you want to assign to the variable identified by `variable_id`.

        """
        if not variable_id:
            return

        try:
            scope, key = variable_id.split(".")
        except ValueError:
            scope = "route"
            key = variable_id

        self.log.debug(
            f"Saving variable [{variable_id}] to room [{self.room_id}] in scope {scope} "
            f":: content [{value}]"
        )

        if scope == "room":
            self.variables = json.dumps(self._variables)
            await self.update()
        else:
            new_variables = self.route._variables
            new_variables[key] = value
            self.route.variables = json.dumps(new_variables)
            await self.route.update()

    async def set_variables(self, variables: Dict) -> None:
        """It takes a dictionary of variable IDs and values, and sets the variables to the values

        Parameters
        ----------
        variables : Dict
            A dictionary of variable names and values.

        """
        for variable in variables:
            await self.set_variable(variable_id=variable, value=variables[variable])

    async def update_menu(self, node_id: str, state: Optional[RouteState] = None):
        """Updates the menu's node_id and state.

        Parameters
        ----------
        node_id : str
            The node_id of the menu. This is used to determine which node display.
        state : Optional[RouteState]
            The state of the menu.
        """
        self.log.debug(
            f"The [room: {self.room_id}] will update his [node: {self.route.node_id}] to [{node_id}] "
            f"and his [state: {self.route.state}] to [{state}]"
        )
        self.route.node_id = node_id
        self.route.state = state
        await self.route.update()
