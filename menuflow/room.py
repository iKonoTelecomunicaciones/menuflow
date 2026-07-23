from __future__ import annotations

from asyncio import Future, Lock
from collections import defaultdict
from logging import getLogger
from re import match
from typing import TYPE_CHECKING, Any, cast

from glom import Delete, PathAccessError, assign, glom
from mautrix.errors.request import MNotFound
from mautrix.types import EventType, Member, RoomID, StateEvent, StateEventContent, UserID
from mautrix.types.util.obj import Obj
from mautrix.util.async_getter_lock import async_getter_lock
from mautrix.util.logging import TraceLogger

from .config import Config
from .db.room import Room as DBRoom
from .db.route import Route, RouteState
from .repository.room_events import RoomEvents
from .scope import Scope
from .utils import JQ2Glom, Util
from .utils.types import Scopes

if TYPE_CHECKING:
    from .matrix import MatrixHandler


class Room(DBRoom):
    by_room_id: dict[(RoomID, UserID), "Room"] = {}
    pending_invites: dict[RoomID, Future] = {}
    _async_get_locks: dict[Any, Lock] = defaultdict(lambda: Lock())
    # Pattern to match the customer's Mxid
    _customer_pattern: str = r"^@.+_(?P<customer_phone>[0-9]{8,}):.+$"
    # Pattern to match the ghost's id
    _ghost_pattern: str = r"^(?P<customer_phone>[0-9]{8,})@s\..+$"
    # Pattern to match the puppet's Mxid
    _puppet_pattern: str = r"^@acd[0-9]+:.+$"
    # JQ2Glom instance
    _jq2glom: JQ2Glom = JQ2Glom()
    _reserved_scopes: set[str] = set(Scopes._value2member_map_)

    config: Config
    log: TraceLogger = getLogger("menuflow.room")

    def __init__(
        self,
        room_id: RoomID,
        id: int = None,
        variables: str = "{}",
        events: dict = {},
    ) -> None:
        super().__init__(id=id, room_id=room_id, variables=f"{variables}", events=events)
        self.log = self.log.getChild(self.room_id)
        self.bot_mxid: UserID = None
        self.route: Route = None
        self.matrix_client: MatrixHandler | None = None
        self.room_events: RoomEvents = None
        self.scope: Scope = Scope(room=self)

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
        bridge_state_event: list[StateEvent] | None = None
        try:
            bridge_state_event = await self.matrix_client.get_state_event(
                room_id=self.room_id, event_type=bridge_event
            )
        except MNotFound as e:
            self.log.error(f"[{self.room_id}] Event {bridge_event} not found: {e}")

        if not bridge_state_event:
            state_key = self.config["menuflow.mautrix_state_key"]

            try:
                bridge_state_event = await self.matrix_client.get_state_event(
                    room_id=self.room_id,
                    event_type=bridge_event,
                    state_key=state_key,
                )
            except MNotFound as e:
                self.log.error(
                    f"[{self.room_id}] Event {bridge_event} with state_key {state_key} not found: {e}"
                )
                return

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
    def all_variables(self) -> dict:
        return {**self._variables, **self.route.variables}

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

        room: Room | None = cast(cls, await super().get_by_room_id(room_id))

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

    @classmethod
    def sync_room_vars_cache(
        cls, room_id: RoomID, variables: str, bot_mxid: UserID | None = None
    ) -> None:
        """This function updates the room variables cache for all bot mxids.

        Parameters
        ----------
        room_id : RoomID
            The room's ID.
        variables : str
            The variables to update.
        bot_mxid : UserID|None
            The bot's Mxid. If None, all bot mxids will be updated.
        """
        for (_bot_mxid, _room_id), room in cls.by_room_id.items():
            if _room_id == room_id and _bot_mxid != bot_mxid:
                room.variables = variables
                room.clear_vars_cache()

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
        scope, key = Util.get_scope_and_key(
            variable_id=variable_id,
            custom_scopes=self.all_variables.keys() - self._reserved_scopes,
            reserved_scopes=self._reserved_scopes,
        )

        # TODO: Remove when the old variables have been fully migrated to the new scopes.
        if scope == Scopes.ROUTE.value:
            scope, key = self.resolve_legacy_var(key, "GET")

        _msg = f"[VAR][GET] {scope}.{key}"
        try:
            _value = glom(self.all_variables, self._jq2glom.to_glom_path(f"{scope}.{key}"))
            self.log.debug(f"{_msg} => {repr(_value)}")
            return _value
        except PathAccessError as e:
            self.log.debug(f"{_msg} => Not found")
            return None
        except Exception as e:
            self.log.error(f"{_msg} => {e}")
            return

    async def set_variable(self, variable_id: str, value: Any, scope: str | None = None) -> None:
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

        if scope:
            key = variable_id
        else:
            scope, key = Util.get_scope_and_key(
                variable_id=variable_id,
                custom_scopes=self.all_variables.keys() - self._reserved_scopes,
                reserved_scopes=self._reserved_scopes,
            )

            # TODO: Remove when the old variables have been fully migrated to the new scopes.
            if scope == Scopes.ROUTE.value:
                scope, key = self.resolve_legacy_var(key, "SET")

        new_variables = self.scope.get(scope)
        new_value = value.serialize() if isinstance(value, Obj) else value

        _msg = f"[VAR][SET] {scope}.{key}"
        try:
            assign(new_variables, self._jq2glom.to_glom_path(key), new_value, missing=dict)
            self.log.debug("%s = %r", _msg, new_value)
        except Exception as e:
            self.log.error("%s => %s", _msg, e)
            return

        await self.scope.update(scope)

    async def set_variables(self, variables: dict) -> None:
        """It takes a dictionary of variable IDs and values, and sets the variables to the values

        Parameters
        ----------
        variables : dict
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

        scope, key = Util.get_scope_and_key(
            variable_id=variable_id,
            custom_scopes=self.all_variables.keys() - self._reserved_scopes,
            reserved_scopes=self._reserved_scopes,
        )

        # TODO: Remove when the old variables have been fully migrated to the new scopes.
        if scope == Scopes.ROUTE.value:
            scope, key = self.resolve_legacy_var(key, "DEL")

        variables = self.scope.get(scope)
        if not variables:
            self.log.debug(f"Variables in scope {scope} are empty")
            return

        _msg = f"[VAR][DEL] {scope}.{key}"
        try:
            glom(variables, Delete(self._jq2glom.to_glom_path(key)))
            self.log.debug(f"{_msg} => Deleted")
        except PathAccessError as e:
            self.log.debug(f"{_msg} => Not found")
            return
        except Exception as e:
            self.log.error(f"{_msg} => {e}")
            return

        await self.scope.update(scope)

    async def del_variables(self, variables: list = []) -> None:
        """This function delete the variables in the room.

        Parameters
        ----------
            variables: list
                The variables to delete.
        """
        for variable in variables:
            await self.del_variable(variable_id=variable)

    async def update_menu(
        self, node_id: str, state: RouteState | None = None, update_node_vars: bool = True
    ):
        """Updates the menu's node_id and state.

        Parameters
        ----------
        node_id : str
            The node_id of the menu. This is used to determine which node display.
        state : RouteState | None
            The state of the menu.
        """
        self.log.debug(
            f"({self.bot_mxid}) will be updated. "
            f"Node: ([{self.route.node_id}] => [{node_id}]) "
            f"State: ([{self.route.state}] => [{state}])"
        )
        if update_node_vars and self.route.node_id != node_id:
            self.scope.clear(Scopes.NODE)

        self.route.node_id = node_id.value if isinstance(node_id, RouteState) else node_id
        self.route.state = state
        await self.route.update()

    def set_node_var(self, **kwargs) -> None:
        """Updates the node variables.

        Parameters
        ----------
        **kwargs : dict
            The node variables to update.
        """
        self.scope.get(Scopes.NODE).update(kwargs)

    @property
    def conversation_uuid(self) -> str | None:
        """This function retrieves the conversation UUID from the room's variables.

        Returns
        -------
            The conversation UUID is being returned as a string or None.
        """
        return self.all_variables.get("room", {}).get("conversation_uuid")

    async def set_conversation_variables(self, variables: dict) -> None:
        """Deletes the conversation variables and sets the new ones.

        Parameters
        ----------
        variables : dict
            A dictionary of variable names and values.

        """
        scope = "conversation"
        if self.scope.get(scope):
            self.log.debug(f"[{self.room_id}] Cleaning conversation variables")
            self.scope.clear(scope)
            await self.scope.update(scope)

        for variable in variables:
            await self.set_variable(variable_id=f"{scope}.{variable}", value=variables[variable])

    # TODO: Remove when the old variables have been fully migrated to the new scopes.
    def resolve_legacy_var(self, key: str, type: str) -> tuple[str, str]:
        """This function resolves the legacy variables to the new scopes.

        Parameters
        ----------
        scope : str
            The scope of the variable.
        key : str
            The key of the variable.
        type : str
            The type of the operation (GET, SET, DEL).

        Returns
        -------
            A tuple containing the new scope and key.
        """
        scope = Scopes.ROUTE.value

        if hasattr(self, "config"):
            for old_key, new_key_dict in self.config.get(
                "menuflow.legacy_route_var_aliases", {}
            ).items():
                new_scope, new_key = new_key_dict["scope"], new_key_dict["key"]

                is_prefix = not new_key and key.startswith(f"{old_key}.")
                is_exact = key == old_key

                if is_prefix or is_exact:
                    self.log.error(
                        f"[VAR][{type}] {scope}.{old_key} is deprecated. Use {new_scope}.{new_key} to {type} variable."
                    )
                    scope = new_scope
                    key = key.replace(f"{old_key}.", new_key, 1) if is_prefix else new_key
                    break

        return scope, key
