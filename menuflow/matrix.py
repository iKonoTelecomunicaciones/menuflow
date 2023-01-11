from __future__ import annotations

import asyncio
from ast import Dict
from copy import deepcopy
from typing import Optional

from mautrix.client import Client as MatrixClient
from mautrix.types import (
    JSON,
    Membership,
    MemberStateEventContent,
    MessageEvent,
    RoomID,
    StateUnsigned,
    StrippedStateEvent,
)

from .config import Config
from .flow import Flow
from .room import Room
from .user import User


class MatrixHandler(MatrixClient):

    LAST_JOIN_EVENT: Dict[RoomID, int] = {}
    LOCKED_ROOMS = set()

    def __init__(self, config: Config, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = config
        flow = Config(path=f"/data/flows/{self.mxid}.yaml", base_path="")
        flow.load()
        self.flow = Flow.deserialize(flow["menu"])

    def handle_sync(self, data: JSON) -> list[asyncio.Task]:
        # This is a way to remove duplicate events from the sync
        aux_data = deepcopy(data)
        for room_id, room_data in aux_data.get("rooms", {}).get("join", {}).items():
            for i in range(len(room_data.get("timeline", {}).get("events", [])) - 1, -1, -1):
                evt = room_data.get("timeline", {}).get("events", [])[i]
                if (
                    self.LAST_JOIN_EVENT.get(room_id)
                    and evt.get("origin_server_ts") <= self.LAST_JOIN_EVENT[room_id]
                ):
                    del data["rooms"]["join"][room_id]["timeline"]["events"][i]
                    continue

                if (
                    evt.get("type", "") == "m.room.member"
                    and evt.get("state_key", "") == self.mxid
                ):
                    if evt.get("content", {}).get("membership") == "join":
                        self.LAST_JOIN_EVENT[room_id] = evt.get("origin_server_ts")

        return super().handle_sync(data)

    async def handle_member(self, evt: StrippedStateEvent) -> None:
        unsigned = evt.unsigned or StateUnsigned()
        prev_content = unsigned.prev_content or MemberStateEventContent()
        prev_membership = prev_content.membership if prev_content else None

        if evt.state_key == self.mxid and evt.content.membership == Membership.INVITE:
            await self.handle_invite(evt)
        elif (
            evt.content.membership == Membership.JOIN
            and prev_membership != Membership.JOIN
            and evt.state_key == self.mxid
        ):
            await self.handle_join(evt)
        elif evt.content.membership == Membership.LEAVE:
            if prev_membership == Membership.JOIN:
                await self.handle_leave(evt)

    async def handle_invite(self, evt: StrippedStateEvent):
        if evt.sender in self.config["menuflow.users_ignore"] or evt.sender == self.mxid:
            self.log.debug(f"This incoming invite event from {evt.room_id} will be ignored")
            return

        await self.join_room(evt.room_id)

    def unlock_room(self, room_id: RoomID):
        self.log.debug(f"UNLOCKING ROOM... {room_id}")
        self.LOCKED_ROOMS.discard(room_id)

    def lock_room(self, room_id: RoomID):
        self.log.debug(f"LOCKING ROOM... {room_id}")
        self.LOCKED_ROOMS.add(room_id)

    async def handle_join(self, evt: StrippedStateEvent):
        if evt.room_id in self.LOCKED_ROOMS:
            self.log.debug(f"Ignoring menu request in {evt.room_id} Menu locked")
            return

        self.log.debug(f"{evt.state_key} ACCEPTED -- EVENT JOIN ... {evt.room_id}")
        self.lock_room(evt.room_id)

        try:
            room = await Room.get_by_room_id(room_id=evt.room_id)
            room.config = self.config
        except Exception as e:
            self.log.exception(e)
            self.unlock_room(evt.room_id)
            return

        await self.algorithm(room=room)

    async def handle_leave(self, evt: StrippedStateEvent):
        room = await Room.get_by_room_id(room_id=evt.room_id, create=False)
        await room.clean_up()
        self.unlock_room(evt.room_id)

    async def handle_message(self, message: MessageEvent) -> None:

        self.log.debug(
            f"Incoming message [user: {message.sender}] [message: {message.content.body}] [room_id: {message.room_id}]"
        )

        # Message edits are ignored
        if message.content._relates_to and message.content._relates_to.rel_type:
            return

        # Ignore bot messages
        if message.sender in self.config["menuflow.users_ignore"] or message.sender == self.mxid:
            self.log.debug(
                f"This incoming message from {message.room_id} will be ignored :: {message.content.body}"
            )
            return

        try:
            user: User = await User.get_by_mxid(mxid=message.sender)
            room = await Room.get_by_room_id(room_id=message.room_id)
            room.config = user.config = self.config

            if not await room.get_varibale("customer_phone") and user.phone:
                await room.set_variable("customer_phone", user.phone)

            if not await room.get_varibale("bot_mxid"):
                await room.set_variable("bot_mxid", self.mxid)
        except Exception as e:
            self.log.exception(e)
            return

        if not room:
            return

        await self.algorithm(room=room, evt=message)

    async def algorithm(self, room: Room, evt: Optional[MessageEvent] = None) -> None:
        """If the room is in the input state, then set the variable to the room's input,
        and if the node has an output connection, then update the menu to the output connection.
        Otherwise, run the node and update the menu to the output connection.
        If the node is an input node and the room is not in the input state,
        then show the message and update the menu to the node's id and set the state to input.
        If the node is a message node, then show the message and if the node has an output connection,
        then update the menu to the output connection and run the algorithm again

        Parameters
        ----------
        room : Room
            Room - the room object
        evt : MessageEvent
            The event that triggered the algorithm.

        Returns
        -------
            The return value is the result of the last expression in the function body.

        """

        # This is the case where the room is in the input state.
        # In this case, the variable is set to the room's input, and if the node has an output connection,
        # then the menu is updated to the output connection.
        # Otherwise, the node is run and the menu is updated to the output connection.

        node = self.flow.node(room=room)

        if node is None:
            self.log.debug(f"Room {room.room_id} does not have a node")
            await room.update_menu(node_id="start")
            return

        self.log.debug(f"The [room: {room.room_id}] [node: {node.id}] [state: {room.state}]")

        if room.state == "input":
            self.log.debug(f"Creating [variable: {node.variable}] [content: {evt.content.body}]")
            try:
                await room.set_variable(
                    node.variable,
                    int(evt.content.body) if evt.content.body.isdigit() else evt.content.body,
                )
            except ValueError as e:
                self.log.warning(e)

            # If the node has an output connection, then update the menu to the output connection.
            # Otherwise, run the node and update the menu to the output connection.

            await room.update_menu(node_id=node.o_connection or await node.run())

        node = self.flow.node(room=room)

        if node.type == "switch":
            await room.update_menu(await node.run())

        node = self.flow.node(room=room)

        # This is the case where the room is not in the input state and the node is an input node.
        # In this case, the message is shown and the menu is updated to the node's id and the state is set to input.
        if node and node.type == "input" and room.state != "input":
            self.log.debug(f"Room {room.room_id} enters input node {node.id}")
            await node.show_message(room_id=room.room_id, client=self)
            await room.update_menu(node_id=node.id, state="input")
            return

        # Showing the message and updating the menu to the output connection.
        if node and node.type == "message":
            self.log.debug(f"Room {room.room_id} enters message node {node.id}")
            await node.show_message(room_id=room.room_id, client=self)

            await room.update_menu(
                node_id=node.o_connection, state="end" if not node.o_connection else None
            )

        node = self.flow.node(room=room)

        if node and node.type == "http_request":
            self.log.debug(f"Room {room.room_id} enters http_request node {node.id}")
            try:
                status, response = await node.request(session=self.api.session)
                self.log.info(f"http_request node {node.id} had a status of {status}")
                if not status in [200, 201]:
                    self.log.error(response)
            except Exception as e:
                self.log.exception(e)
                return

        node = self.flow.node(room=room)

        if room.state == "end":
            self.log.debug(f"The room {room.room_id} has terminated the flow")
            await room.update_menu(node_id="start")
            return

        await self.algorithm(room=room, evt=evt)
