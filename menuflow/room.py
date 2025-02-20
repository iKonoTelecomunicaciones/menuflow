from __future__ import annotations

import json
from asyncio import Future, Lock
from collections import defaultdict
from logging import getLogger
from re import match
from typing import Any, Dict, List, Optional, cast

from mautrix.client import Client as MatrixClient
from mautrix.types import EventType, Member, RoomID, StateEvent, StateEventContent, UserID
from mautrix.types.util.obj import Obj
from mautrix.util.async_getter_lock import async_getter_lock
from mautrix.util.logging import TraceLogger

from .config import Config
from .db.room import Room as DBRoom
from .db.route import Route, RouteState
from .utils import Util


class Room(DBRoom):
    by_room_id: Dict[(RoomID, UserID), "Room"] = {}
    pending_invites: Dict[RoomID, Future] = {}
    _async_get_locks: dict[Any, Lock] = defaultdict(lambda: Lock())
    # Pattern to match the customer's Mxid
    _customer_pattern: str = r"^@.+_(?P<customer_phone>[0-9]{8,}):.+$"
    # Pattern to match the ghost's id
    _ghost_pattern: str = r"^(?P<customer_phone>[0-9]{8,})@s\..+$"
    # Pattern to match the puppet's Mxid
    _puppet_pattern: str = r"^@acd[0-9]+:.+$"

    config: Config
    log: TraceLogger = getLogger("menuflow.room")

    def __init__(
        self,
        room_id: RoomID,
        id: int = None,
        variables: str = "{}",
    ) -> None:
        self._variables: Dict = json.loads(variables)
        super().__init__(id=id, room_id=room_id, variables=f"{variables}")
        self.log = self.log.getChild(self.room_id)
        self.bot_mxid: UserID = None
        self.route: Route = None
        self.matrix_client: MatrixClient = None

    @property
    async def get_ghost_number(self) -> str | None:
        """
        This function retrieves the ghost's phone number from the room's state events.

        Returns
        -------
            The ghost's phone number is being returned as a string or None.
        """
        # Create the m.bridge event type to filter the state events
        bridge_event: EventType = EventType(t="m.bridge", t_class=EventType.Class.STATE)
        # Get the m.bridge state event and get the customer's Mxid
        bridge_state_event: list[StateEvent] = await self.matrix_client.get_state_event(
            room_id=self.room_id, event_type=bridge_event
        )

        # Check if the m.bridge state event has the customer's Mxid
        if bridge_state_event and bridge_state_event.channel:
            bridge_channel = bridge_state_event.channel
            match_ghost = match(pattern=self._ghost_pattern, string=bridge_channel.id or "")

            # Check if the bridge channel's id is a ghost Mxid
            if bridge_channel and bridge_channel.id and bool(match_ghost):
                self.log.debug(f"Customer {bridge_channel.id} is a ghost Mxid")
                # Get the phone number from the ghost Mxid
                return match_ghost.group("customer_phone")

        return

    async def get_customer_mxid_by_phone(self, phone_number: str) -> str | None:
        """
        This function retrieves the customer's Mxid using the phone number.

        Parameters
        ----------
        phone_number : str
            The phone number of the customer.

        Returns
        -------
            The customer's Mxid is being returned as a string or None.
        """
        # Get the members of the room
        members: list[Member] = await self.matrix_client.get_members(room_id=self.room_id)

        # Get the customer's Mxid using the phone number
        for member in members:
            member_mxid: str = member.state_key
            match_customer = match(pattern=self._customer_pattern, string=member_mxid)
            if member_mxid and bool(match_customer):
                # Get the phone number from the customer's Mxid (it is like
                # @whatsapp_12345678:domain)
                member_phone: str = match_customer.group("customer_phone")
                if member_phone == phone_number:
                    # Return the customer's Mxid
                    return member_mxid

        return

    @property
    async def customer_mxid(self) -> UserID | None:
        """This function retrieves the customer of a Matrix room.

        Returns
        -------
            The `customer` of the Matrix room is being returned as a string.

        """
        # Search the creator in the room's state events
        created_room_event: StateEventContent = await self.matrix_client.get_state_event(
            room_id=self.room_id, event_type=EventType.ROOM_CREATE
        )

        # Get the creator of the room
        room_creator = created_room_event.get("creator")

        # Check if the creator is the customer. This is valid for whatsapp mautrix bridge
        # version < 0.11.0
        if room_creator and bool(match(pattern=self._customer_pattern, string=room_creator)):
            self.log.debug(f"Creator {room_creator} is a customer")
            return room_creator

        # Get the ghost's phone numbe. This is valid for whatsapp mautrix bridge version >= 0.11.0
        ghost_number: str = await self.get_ghost_number
        if not ghost_number:
            return

        # Return the customer's Mxid using the phone number
        return await self.get_customer_mxid_by_phone(phone_number=ghost_number)

    @property
    async def get_puppet_mxid(self) -> str:
        """
        This function retrieves the puppet's Mxid from the room's state events.

        Returns
        -------
            The puppet's Mxid is being returned as a string.
        """
        # Get the members of the room
        members: list[Member] = await self.matrix_client.get_members(room_id=self.room_id)

        # Get the puppet's Mxid
        for member in members:
            member_mxid: str = member.state_key
            match_puppet = match(pattern=self._puppet_pattern, string=member_mxid)
            if member_mxid and bool(match_puppet):
                self.log.debug(f"Member {member_mxid} is a puppet Mxid")
                return member_mxid

        return

    @property
    def all_variables(self) -> Dict:
        return {"room": self._variables, "route": self.route._variables}

    @classmethod
    @async_getter_lock
    async def get_by_room_id(
        cls, room_id: RoomID, bot_mxid: UserID, create: bool = True
    ) -> "Room" | None:
        """It gets a room from the database, or creates one if it doesn't exist

        Parameters
        ----------
        room_id : RoomID
            The room's ID.
        bot_mxid : UserID
            The bot's Mxid.
        create : bool, optional
            If True, the room will be created if it doesn't exist.

        Returns
        -------
            The room object

        """

        try:
            room = cls.by_room_id[(bot_mxid, room_id)]
            room.bot_mxid = bot_mxid
            room.route = await Route.get_by_room_and_client(room=room.id, client=bot_mxid)
            return room
        except KeyError:
            pass

        room = cast(cls, await super().get_by_room_id(room_id))

        if room is not None:
            room.bot_mxid = bot_mxid
            room.route = await Route.get_by_room_and_client(room=room.id, client=bot_mxid)
            room._add_to_cache(bot_mxid=bot_mxid)
            return room

        if create:
            room = cls(room_id=room_id)
            await room.insert()
            room = cast(cls, await super().get_by_room_id(room_id))
            room.bot_mxid = bot_mxid
            room.route = await Route.get_by_room_and_client(room=room.id, client=bot_mxid)
            room._add_to_cache(bot_mxid=bot_mxid)
            return room

    def _add_to_cache(self, bot_mxid: UserID) -> None:
        if self.room_id:
            self.by_room_id[(bot_mxid, self.room_id)] = self

    async def clean_up(self):
        await Util.cancel_task(task_name=self.room_id)
        await self.route.clean_up()

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
        try:
            scope, key = variable_id.split(".", 1)
        except ValueError:
            scope = "route"
            key = variable_id

        return self.all_variables.get(scope, {}).get(key, None)

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

        new_variables = self._variables if scope == "room" else self.route._variables
        if isinstance(value, Obj):
            new_variables[key] = value.serialize()
        else:
            new_variables[key] = value

        if scope == "room":
            self.variables = json.dumps(new_variables)
        else:
            self.route.variables = json.dumps(new_variables)
        await self.update() if scope == "room" else await self.route.update()

    async def set_variables(self, variables: Dict) -> None:
        """It takes a dictionary of variable IDs and values, and sets the variables to the values

        Parameters
        ----------
        variables : Dict
            A dictionary of variable names and values.

        """
        for variable in variables:
            await self.set_variable(variable_id=variable, value=variables[variable])

    async def del_variable(self, variable_id: str) -> None:
        """The function delete a variable in either the room or route scope
        and updates the corresponding JSON data.

        Parameters
        ----------
        variable_id : str
            The `variable_id` parameter is a string that represents the identifier of the variable you want to set.
            It can be in the format "scope.key" or just "key".
            The "scope" indicates the scope of the variable (e.g., "room" or "route")."
        """
        if not variable_id:
            return

        try:
            scope, key = variable_id.split(".")
        except ValueError:
            scope = "route"
            key = variable_id

        variables: Dict = self._variables if scope == "room" else self.route._variables
        if not variables:
            self.log.debug(f"Variables in the room {self.room_id} are empty")
            return

        if variables and not variables.get(key):
            self.log.debug(f"Variable [{variable_id}] does not exists in the room {self.room_id}")
            return

        self.log.debug(
            f"Removing variable [{key}] to room [{self.room_id}] in scope {scope}"
            f":: content [{variables.get(key)}]"
        )
        variables.pop(key, None)
        if scope == "room":
            self.variables = json.dumps(variables)
        else:
            self.route.variables = json.dumps(variables)
        await self.update() if scope == "room" else await self.route.update()

    async def del_variables(self, variables: List = []) -> None:
        """This function delete the variables in the room.

        Parameters
        ----------
            variables: List
                The variables to delete.
        """
        for variable in variables:
            await self.del_variable(variable_id=variable)

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
            f"The [room: {self.room_id}] with route [{self.bot_mxid}] will update his [node: "
            f"{self.route.node_id}] to [{node_id}] and his [state: {self.route.state}] to [{state}]"
        )
        self.route.node_id = node_id
        self.route.state = state
        await self.route.update()
