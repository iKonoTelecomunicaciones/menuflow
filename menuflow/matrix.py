from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Dict, Optional

import yaml
from mautrix.client import Client as MatrixClient
from mautrix.types import (
    JSON,
    Membership,
    MemberStateEventContent,
    MessageEvent,
    MessageType,
    RoomID,
    StateUnsigned,
    StrippedStateEvent,
)

from .config import Config
from .db.room import RoomState
from .flow import Flow
from .nodes import Base, CheckTime, HTTPRequest, Input, Media, Message, Switch
from .repository import Flow as FlowModel
from .room import Room
from .user import User
from .utils import Util


class MatrixHandler(MatrixClient):
    LAST_JOIN_EVENT: Dict[RoomID, int] = {}
    LOCKED_ROOMS = set()

    def __init__(self, config: Config, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = config
        path = f"/data/flows/{self.mxid}.yaml"
        flow = Config(path=path, base_path="")
        try:
            flow.load()
        except FileNotFoundError as e:
            self.log.warning(e)
            with open(path, "a") as yaml_file:
                yaml.dump(Util.flow_example(), yaml_file)

            self.log.warning(
                f"Please configure your {self.mxid}.yaml file and restart the service"
            )
            flow.load()

        self.util = Util(self.config)
        self.flow = Flow(flow_data=FlowModel.deserialize(flow["menu"]))
        Base.init_cls(
            config=self.config, matrix_client=self, default_variables=self.flow.flow_variables
        )
        self.flow.load()

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
        if self.util.ignore_user(mxid=evt.sender, origin="invite") or evt.sender == self.mxid:
            self.log.debug(f"This incoming invite event from {evt.room_id} will be ignored")
            await self.leave_room(evt.room_id)
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
            if not await room.get_variable("bot_mxid"):
                await room.set_variable("bot_mxid", self.mxid)
                await room.set_variable("customer_room_id", evt.room_id)
        except Exception as e:
            self.log.exception(e)
            self.unlock_room(evt.room_id)
            return

        await self.algorithm(room=room)

    async def handle_leave(self, evt: StrippedStateEvent):
        room = await Room.get_by_room_id(room_id=evt.room_id, create=False)

        if not room:
            return

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
        if (
            self.util.ignore_user(mxid=message.sender, origin="message")
            or message.sender == self.mxid
            or message.content.msgtype == MessageType.NOTICE
        ):
            self.log.debug(
                f"This incoming message from {message.room_id} will be ignored :: {message.content.body}"
            )
            return

        try:
            user: User = await User.get_by_mxid(mxid=message.sender)
            room = await Room.get_by_room_id(room_id=message.room_id)
            room.config = user.config = self.config

            if not await room.get_variable("customer_phone") and user.phone:
                await room.set_variable("customer_phone", user.phone)

        except Exception as e:
            self.log.exception(e)
            return

        if not room:
            return

        await self.algorithm(room=room, evt=message)

    async def algorithm(self, room: Room, evt: Optional[MessageEvent] = None) -> None:
        """The algorithm function is the main function that runs the flow.
        It takes a room and an event as parameters

        Parameters
        ----------
        room : Room
            The room object.
        evt : Optional[MessageEvent]
            The event that triggered the algorithm.
        """

        node = self.flow.node(room=room)

        if node is None:
            self.log.debug(f"Room {room.room_id} does not have a node")
            await room.update_menu(node_id=RoomState.START)
            return

        self.log.debug(f"The [room: {room.room_id}] [node: {node.id}] [state: {room.state}]")

        if type(node) == CheckTime:
            await node.run()

        node = self.flow.node(room=room)

        if type(node) == Input:
            await node.run(evt=evt)
            if room.state == RoomState.INPUT:
                return

        node = self.flow.node(room=room)

        if type(node) == Message:
            await node.run()

        node = self.flow.node(room=room)

        if type(node) == Media:
            await node.run()

        node = self.flow.node(room=room)

        if type(node) == HTTPRequest:
            await node.run()

        node = self.flow.node(room=room)

        if type(node) == Switch:
            await node.run()

        node = self.flow.node(room=room)

        if room.state == RoomState.END:
            self.log.debug(f"The room {room.room_id} has terminated the flow")
            await room.update_menu(node_id=RoomState.START)
            return

        await self.algorithm(room=room, evt=evt)
