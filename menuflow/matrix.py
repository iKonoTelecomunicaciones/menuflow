from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Optional

from mautrix.client import Client as MatrixClient
from mautrix.types import (
    Membership,
    MemberStateEventContent,
    MessageEvent,
    MessageType,
    RelationType,
    RoomID,
    StateUnsigned,
    StrippedStateEvent,
    UserID,
)

from .config import Config
from .db.route import RouteState
from .nodes import Base, FormInput, GPTAssistant, Input, InteractiveInput
from .room import Room
from .user import User
from .utils import Util

if TYPE_CHECKING:
    from .flow import Flow, Node
    from .repository import FlowUtils


class MatrixHandler(MatrixClient):
    message_group_by_room: Dict[RoomID, list[MessageEvent]] = {}
    ROOMS_TRACEBACK: Dict = {}

    def __init__(
        self, config: Config, flow: Flow, flow_utils: Optional[FlowUtils] = None, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.config = config
        self.flow_utils = flow_utils
        self.util = Util(self.config)
        self.flow = flow
        self.LOCKED_ROOMS = set()
        self.LAST_JOIN_EVENT: Dict[RoomID, int] = {}
        self.LAST_RECEIVED_MESSAGE: Dict[RoomID, datetime] = {}
        Base.init_cls(
            config=self.config,
            session=self.api.session,
        )

    def handle_sync(self, data: Dict) -> list[asyncio.Task]:
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

    def unlock_room(self, room_id: RoomID):
        self.log.debug(f"UNLOCKING ROOM... {room_id}")
        self.LOCKED_ROOMS.discard(room_id)

    def lock_room(self, room_id: RoomID):
        self.log.debug(f"LOCKING ROOM... {room_id}")
        self.LOCKED_ROOMS.add(room_id)

    async def handle_member(self, evt: StrippedStateEvent) -> None:
        unsigned = evt.unsigned or StateUnsigned()
        prev_content = unsigned.prev_content or MemberStateEventContent()
        prev_membership = prev_content.membership if prev_content else None

        if evt.state_key == self.mxid and evt.content.membership == Membership.INVITE:
            await self.handle_invite(evt)
        elif evt.content.membership == Membership.JOIN and prev_membership != Membership.JOIN:
            await self.handle_join(evt)
        elif evt.content.membership == Membership.LEAVE:
            if evt.state_key == self.mxid:
                self.unlock_room(room_id=evt.room_id)

            if prev_membership == Membership.INVITE:
                await self.handle_reject_invite(evt)

    async def handle_invite(self, evt: StrippedStateEvent):
        if self.util.ignore_user(mxid=evt.sender, origin="invite") or evt.sender == self.mxid:
            self.log.debug(f"This incoming invite event from {evt.room_id} will be ignored")
            await self.leave_room(evt.room_id)
            return

        self.unlock_room(room_id=evt.room_id)
        await self.join_room(evt.room_id)

    async def handle_reject_invite(self, evt: StrippedStateEvent):
        if evt.room_id in Room.pending_invites:
            if not Room.pending_invites[evt.room_id].done():
                Room.pending_invites[evt.room_id].set_result(False)

    async def load_all_room_constants(self):
        """This function loads room constants for joined rooms in a Matrix chat using Python.

        Returns
        -------
            If there are no joined rooms, the function will return nothing.
            If there are joined rooms, the function will execute the code block and return nothing.

        """

        joined_room = await self.get_joined_rooms()

        if not joined_room:
            return

        self.log.debug("Loading rooms constants ...")

        for joined_room in joined_room:
            await self.load_room_constants(room_id=joined_room)

    async def load_room_constants(self, room_id: RoomID):
        """This function loads constants for a given room and sets variables if they do not exist.

        Parameters
        ----------
        room_id : RoomID
            The ID of the Matrix room that the constants are being loaded for.

        """

        room: Room = await Room.get_by_room_id(room_id=room_id, bot_mxid=self.mxid)

        room.config = self.config
        room.matrix_client = self

        if not await room.get_variable(variable_id="customer_room_id"):
            await room.set_variable("customer_room_id", room_id)

        if not await room.get_variable(variable_id="bot_mxid"):
            await room.set_variable("bot_mxid", self.mxid)

        if not await room.get_variable(variable_id="customer_mxid"):
            user_mxid: UserID | None = await room.customer_mxid
            await User.get_by_mxid(mxid=user_mxid)
            await room.set_variable(variable_id="customer_mxid", value=user_mxid)

        if not await room.get_variable(variable_id="puppet_mxid"):
            puppet_mxid: str = await room.get_puppet_mxid
            await room.set_variable(variable_id="puppet_mxid", value=puppet_mxid)

    async def handle_join(self, evt: StrippedStateEvent):
        if evt.room_id in Room.pending_invites:
            if not Room.pending_invites[evt.room_id].done():
                Room.pending_invites[evt.room_id].set_result(True)

        # Ignore all events that are not from the bot
        if not evt.state_key == self.mxid:
            return

        if evt.room_id in self.LOCKED_ROOMS:
            self.log.warning(f"Ignoring menu request in {evt.room_id} Menu locked")
            return

        self.lock_room(evt.room_id)

        self.log.info(f"{evt.state_key} ACCEPTED -- EVENT JOIN ... {evt.room_id}")
        room: Room = await Room.get_by_room_id(room_id=evt.room_id, bot_mxid=self.mxid)
        room.config = self.config
        room.matrix_client = self

        # Clean up the actions
        await room.clean_up()
        if (room.room_id, room.route.id) in GPTAssistant.assistant_cache:
            del GPTAssistant.assistant_cache[(room.room_id, room.route.id)]

        await self.load_room_constants(evt.room_id)
        await self.algorithm(room=room)

    async def handle_message(self, message: MessageEvent) -> None:
        self.log.debug(
            f"Incoming message [user: {message.sender}] [message: {message.content.body}] [room_id: {message.room_id}]"
        )

        if message.room_id not in self.ROOMS_TRACEBACK:
            self.log.debug(f"Adding room {message.room_id} to message traceback")
            self.ROOMS_TRACEBACK[message.room_id] = {
                "message_counter": 0,
                "ignore": False,
                "sometimes_ignored": 0,
                "time_to_ignore": self.config["menuflow.bot_war.time_to_ignore"],
                "running_limit_task": False,
                "running_restore_task": False,
                "task_name": f"{message.room_id}_message_traceback",
            }

        running_limit_task = self.ROOMS_TRACEBACK[message.room_id]["running_limit_task"]
        running_restore_task = self.ROOMS_TRACEBACK[message.room_id]["running_restore_task"]
        task_name = self.ROOMS_TRACEBACK[message.room_id]["task_name"]
        time_to_ignore = self.ROOMS_TRACEBACK[message.room_id]["time_to_ignore"]
        checker_limit_timer = self.config["menuflow.bot_war.init_checker_limit_timer"]

        if running_limit_task is False or running_restore_task is False:
            loop = asyncio.get_event_loop()

        def conversation_status(ignore: Optional[bool] = False):
            if not ignore:
                asyncio.create_task(
                    self.check_message_limit(room_id=message.room_id),
                    name=task_name,
                )
            else:
                asyncio.create_task(
                    self.restore_state(room_id=message.room_id),
                    name=task_name,
                )

        if self.ROOMS_TRACEBACK[message.room_id]["ignore"] is False:

            if running_limit_task is False:
                self.ROOMS_TRACEBACK[message.room_id]["running_limit_task"] = True
                loop.call_later(checker_limit_timer, conversation_status)

            # Message edits are ignored
            if (
                message.content._relates_to
                and message.content._relates_to.rel_type
                and message.content._relates_to.rel_type == RelationType.REPLACE
            ):
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

            current_message_time = datetime.fromtimestamp(message.timestamp / 1000)
            last_message_time = self.LAST_RECEIVED_MESSAGE.get(message.room_id)
            if (
                last_message_time
                and (current_message_time - last_message_time).seconds
                < self.config["menuflow.message_rate_limit"]
            ):
                self.log.warning(f"Message in {message.room_id} ignored due to rate limit")
                return

            self.ROOMS_TRACEBACK[message.room_id]["message_counter"] += 1
            self.LAST_RECEIVED_MESSAGE[message.room_id] = current_message_time
            room: Room = await Room.get_by_room_id(room_id=message.room_id, bot_mxid=self.mxid)
            room.config = self.config = self.config
            room.matrix_client = self

            if not room:
                return

            if room.room_id in Room.pending_invites:
                self.log.warning(f"Ignoring message in {room.room_id} pending invite")
                return

            await self.algorithm(room=room, evt=message)

        else:
            if running_restore_task is False:
                self.log.warning(f"Ignoring messages for {time_to_ignore} seconds...")
                self.ROOMS_TRACEBACK[message.room_id]["running_restore_task"] = True
                loop.call_later(time_to_ignore, conversation_status, True)

    async def check_message_limit(self, room_id: str):
        self.log.debug(f"Checking message limit for room {room_id}...")
        if self.ROOMS_TRACEBACK[room_id]["message_counter"] >= 10:
            self.log.warning(
                f"Message limit reached for room {room_id}, the messages will be ignored"
            )
            self.ROOMS_TRACEBACK[room_id]["ignore"] = True
            self.ROOMS_TRACEBACK[room_id]["sometimes_ignored"] += 1
        else:
            self.ROOMS_TRACEBACK[room_id]["running_limit_task"] = False

    async def restore_state(self, room_id: str):
        self.ROOMS_TRACEBACK[room_id]["ignore"] = False
        self.ROOMS_TRACEBACK[room_id]["message_counter"] = 0
        self.ROOMS_TRACEBACK[room_id]["running_limit_task"] = False
        self.ROOMS_TRACEBACK[room_id]["running_restore_task"] = False

        self.log.warning(f"Restoring state for room {room_id} to unignore messages")
        if (
            self.ROOMS_TRACEBACK[room_id]["sometimes_ignored"]
            == self.config["menuflow.bot_war.sometimes_ignored_threshold"]
        ):
            self.ROOMS_TRACEBACK[room_id]["sometimes_ignored"] = 0
            self.ROOMS_TRACEBACK[room_id]["time_to_ignore"] = self.config[
                "menuflow.bot_war.time_to_ignore"
            ]
            await self.set_room_tag_bot(room_id=room_id)
        else:
            self.ROOMS_TRACEBACK[room_id]["time_to_ignore"] *= self.config[
                "menuflow.bot_war.time_multiplier"
            ]

    async def set_room_tag_bot(self, room_id: str):
        self.log.debug(f"Setting room tag bot for {room_id}...")
        try:
            await self.api.session.put(
                url=f"{self.api.base_url}/_matrix/client/v3/rooms/{room_id}/state/ik.chat.tag/",
                headers={"Authorization": f"Bearer {self.api.token}"},
                json={
                    "tags": [
                        {"id": "!jnMhGVDjyXCShxfQKl:darknet", "text": "bot", "color": "#38d66d"}
                    ]
                },
                params={"user_id": self.mxid},
            )
        except Exception as error:
            self.log.error(f"Error adding tag to portal {room_id}: {error}")

        try:
            await self.api.session.put(
                url=f"{self.api.base_url}/_matrix/client/v3/rooms/!jnMhGVDjyXCShxfQKl:darknet/state/m.space.child/{room_id}",
                headers={"Authorization": f"Bearer {self.api.token}"},
                json={"via": [self.domain], "suggested": False},
            )
        except Exception as error:
            self.log.error(
                f"Error adding portal {room_id} to space !jnMhGVDjyXCShxfQKl:darknet: {error}"
            )

    # async def is_a_bot(self, room_id: str) -> bool:
    #     try:
    #         conversation_tags = await self.api.session.get(
    #             url=f"{self.api.base_url}/_matrix/client/v3/user/{self.mxid}/rooms/{room_id}/tags",
    #             headers={"Authorization": f"Bearer {self.api.token}"},
    #         )
    #     except Exception as error:
    #         self.log.error(f"Error checking if the {room_id} is a bot: {error}")

    #     if conversation_tags:
    #         conversation_tags = await conversation_tags.json()
    #         self.log.critical(f"#################################################################")
    #         self.log.critical(f"{conversation_tags=}")
    #         self.log.critical(f"#################################################################")

    async def group_message(self, room: Room, message: MessageEvent, node: Node) -> bool:
        """This function groups messages together based on the group_messages_timeout parameter.

        Parameters
        ----------
        room_id : RoomID
            The ID of the Matrix room.
        message : MessageEvent
            The message event object.
        node : Node
            The node object.

        Returns
        -------
        bool
            Returns True if the timeout is done, otherwise False.
        """

        message_group = self.message_group_by_room.setdefault(room.room_id, [])
        message_group.append(message)

        async def run_node():
            await node.run(message_group)
            await self.algorithm(room=room)

        def run_sync():
            asyncio.create_task(run_node())

        if len(message_group) == 1:
            loop = asyncio.get_event_loop()
            loop.call_later(node.group_messages_timeout, run_sync)

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
            self.log.debug(f"Room {room.room_id} does not have a node [{node}]")
            await room.update_menu(node_id="start")
            return

        self.log.debug(f"The [room: {room.room_id}] [node: {node.id}] [state: {room.route.state}]")

        if type(node) in (Input, InteractiveInput, FormInput, GPTAssistant):
            if isinstance(node, GPTAssistant) and room.route.state == RouteState.INPUT:
                await self.group_message(room=room, message=evt, node=node)
                return

            if room.room_id in self.message_group_by_room:
                del self.message_group_by_room[room.room_id]

            await node.run(evt)
            if room.route.state == RouteState.INPUT:
                return
        else:
            await node.run()
            if room.route.state == RouteState.INVITE:
                return

        if room.route.state == RouteState.END:
            self.log.debug(f"The room {room.room_id} has terminated the flow")
            await room.update_menu(node_id="start")
            return

        await self.algorithm(room=room, evt=evt)
