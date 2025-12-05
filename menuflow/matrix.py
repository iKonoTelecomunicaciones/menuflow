from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from mautrix.client import Client as MatrixClient
from mautrix.errors.request import MLimitExceeded
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
from .db.room import Room as DBRoom
from .db.route import RouteState
from .nodes import Base, FormInput, GPTAssistant, Input, InteractiveInput, Webhook
from .room import Room
from .user import User
from .utils import Util

if TYPE_CHECKING:
    from .flow import Flow, Node
    from .repository import FlowUtils


@dataclass(slots=True)
class RoomStatus:
    last_join_event: dict = field(default_factory=dict)
    last_processed_message: MessageEvent | None = None
    lock_room: bool | None = None
    queue_message: asyncio.Queue | None = None


class MatrixHandler(MatrixClient):
    message_group_by_room: dict[RoomID, list[MessageEvent]] = {}

    def __init__(
        self, config: Config, flow: Flow, flow_utils: FlowUtils | None = None, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.config = config
        self.flow_utils = flow_utils
        self.util = Util(self.config)
        self.flow = flow
        self.ROOM_STATUS: dict[RoomID, RoomStatus] = {}
        self.LOCKED_ROOMS = set()
        Base.init_cls(
            config=self.config,
            session=self.api.session,
        )

    def handle_sync(self, data: dict) -> list[asyncio.Task]:
        # This is a way to remove duplicate events from the sync
        try:
            rooms = data.get("rooms", {}).get("join", {})
            for room_id, room_data in rooms.items():
                if room_id not in self.ROOM_STATUS:
                    self.ROOM_STATUS[room_id] = RoomStatus()

                last_join_evt = self.ROOM_STATUS[room_id].last_join_event
                events = room_data.get("timeline", {}).get("events", [])
                for evt in events:
                    if (
                        evt.get("type", "") == "m.room.member"
                        and evt.get("state_key", "") == self.mxid
                        and evt.get("content", {}).get("membership") == "join"
                        and evt.get("origin_server_ts") > last_join_evt.get("origin_server_ts", 0)
                    ):
                        last_join_evt = self.ROOM_STATUS[room_id].last_join_event = evt

                # Only the events that occur after the last join event are kept in the event list.
                if _last_join_ts := last_join_evt.get("origin_server_ts", 0):
                    filtered_events = [
                        evt for evt in events if evt.get("origin_server_ts") >= _last_join_ts
                    ]
                    room_data["timeline"]["events"] = filtered_events
        except Exception as e:
            self.log.critical(f"Error handling sync: {e}")

        return super().handle_sync(data)

    def unlock_room(self, room_id: RoomID, evt: StrippedStateEvent = None):
        self.log.debug(
            f"[{room_id}] Unlocking room for event ({evt.event_id if evt else 'unknown'})"
        )
        self.LOCKED_ROOMS.discard(room_id)

    def lock_room(self, room_id: RoomID, evt: StrippedStateEvent = None):
        self.log.debug(
            f"[{room_id}] Locking room for event ({evt.event_id if evt else 'unknown'})"
        )
        self.LOCKED_ROOMS.add(room_id)

    async def handle_member(self, evt: StrippedStateEvent) -> None:
        self.log.info(
            f"[{evt.room_id}] New membership ({evt.content.get('membership')}) "
            f"event ({evt.event_id}) received. Timestamp: {getattr(evt, 'timestamp', 0)}"
        )

        unsigned = evt.unsigned or StateUnsigned()
        prev_content = unsigned.prev_content or MemberStateEventContent()
        prev_membership = prev_content.membership if prev_content else None

        if evt.state_key == self.mxid and evt.content.membership == Membership.INVITE:
            await self.handle_invite(evt)
        elif evt.content.membership == Membership.JOIN and prev_membership != Membership.JOIN:
            await self.handle_join(evt)
        elif evt.content.membership == Membership.LEAVE:
            if evt.state_key == self.mxid:
                await self.handle_leave(evt)
            if prev_membership == Membership.INVITE:
                await self.handle_reject_invite(evt)

    async def handle_leave(self, evt: StrippedStateEvent):
        last_join_evt = self.ROOM_STATUS.get(evt.room_id, RoomStatus()).last_join_event
        if getattr(evt, "timestamp", 0) < last_join_evt.get("origin_server_ts", 0):
            self.log.warning(
                f"[{evt.room_id}] Ignoring {evt.content.get('membership')} event ({evt.event_id}) "
                f"is older than last join event ({last_join_evt.get('event_id')})"
            )
        else:
            self.log.info(
                f"[{evt.room_id}] Handling leave event ({evt.event_id}) for bot ({evt.state_key})"
            )
            room: Room = await Room.get_by_room_id(room_id=evt.room_id, bot_mxid=self.mxid)
            await Util.cancel_task(task_name=room.room_id)
            room.route._node_vars = {}
            await room.route.update()
            self.unlock_room(room_id=evt.room_id, evt=evt)

    async def handle_invite(self, evt: StrippedStateEvent):
        self.log.info(f"[{evt.room_id}] Handling invite event ({evt.event_id})")
        if self.util.ignore_user(mxid=evt.sender, origin="invite") or evt.sender == self.mxid:
            self.log.debug(f"[{evt.room_id}] This incoming invite event will be ignored")
            await self.leave_room(evt.room_id)
            return

        self.unlock_room(room_id=evt.room_id, evt=evt)
        await self.join_room(evt.room_id)

    async def handle_reject_invite(self, evt: StrippedStateEvent):
        self.log.info(f"[{evt.room_id}] Handling reject invite event {evt.event_id}")
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

        await room.set_variable("room.current_bot_mxid", self.mxid)

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
        if evt.room_id in Room.pending_invites and not Room.pending_invites[evt.room_id].done():
            Room.pending_invites[evt.room_id].set_result(True)

        if not evt.state_key == self.mxid:
            self.log.debug(
                f"[{evt.room_id}] Ignoring join event ({evt.event_id}). Not from the bot"
            )
            return

        if evt.room_id not in self.ROOM_STATUS:
            self.ROOM_STATUS[evt.room_id] = RoomStatus()

        last_join_evt = self.ROOM_STATUS[evt.room_id].last_join_event
        membership_evt = evt.content.get("membership")
        if getattr(evt, "timestamp", 0) < last_join_evt.get("origin_server_ts", 0):
            self.log.warning(
                f"[{evt.room_id}] Ignoring {membership_evt} event ({evt.event_id}) "
                f"is older than last join event ({last_join_evt.get('event_id')})"
            )
            return

        if evt.room_id in self.LOCKED_ROOMS:
            if evt.event_id == last_join_evt.get("event_id"):
                msg = "Already processed."
            else:
                msg = "Menu locked."

            self.log.warning(
                f"[{evt.room_id}] Ignoring {membership_evt} event ({evt.event_id}). {msg}"
            )
            return

        self.lock_room(room_id=evt.room_id, evt=evt)
        self.log.info(f"[{evt.room_id}] Join event ({evt.event_id}) from {evt.state_key} accepted")

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
        base = f"[{message.room_id}] Incoming message ({message.event_id}) from {message.sender}"

        if self.log.getEffectiveLevel() <= logging.DEBUG:
            self.log.debug(f"{base}. Content: {repr(message.content.body)}")
        else:
            self.log.info(base)

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
            self.log.warning(
                f"[{message.room_id}] The incoming message ({message.event_id}) from {message.sender} will be ignored by the bot"
            )
            return

        room: Room = await Room.get_by_room_id(room_id=message.room_id, bot_mxid=self.mxid)

        if not room:
            return

        if message.room_id not in self.ROOM_STATUS:
            self.ROOM_STATUS[message.room_id] = RoomStatus()

        last_message_time = self.ROOM_STATUS[message.room_id].last_processed_message
        current_message_time = datetime.fromtimestamp(message.timestamp / 1000)
        if (
            last_message_time
            and (current_message_time - last_message_time).seconds
            < self.config["menuflow.message_rate_limit"]
            and not self.flow.get_node_by_id(node_id=room.route.node_id).get("type")
            == "gpt_assistant"
        ):
            self.log.warning(f"[{message.room_id}] Message ignored due to rate limit")
            return

        self.ROOM_STATUS[message.room_id].last_processed_message = current_message_time
        room.config = self.config = self.config
        room.matrix_client = self

        # TODO: Review this logic to ignore messages in pending invites.
        if room.room_id in Room.pending_invites:
            self.log.warning(f"[{room.room_id}] Ignoring message in pending invite")
            return

        # TODO: Review this logic to cancel the inactivity task if it exists
        # node = self.flow.node(room=room)
        #
        # if node and room.route._node_vars.get("inactivity"):
        # self.log.info(f"[{room.room_id}] Inactivity config detected")
        # await Util.cancel_task(task_name=room.room_id)
        # if not isinstance(node, Webhook):
        # room.set_node_var(inactivity={})
        # await room.route.update_node_vars()

        queue = self.publish_event(message=message, room_id=room.room_id)

        # TODO: Review this logic
        if not queue:
            await self.algorithm(room=room, evt=message)

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
            self.log.info(
                f"Time's up, sending group message [room: {room.room_id}] [node: {node.id}] [messages: {len(message_group)}]"
            )
            asyncio.create_task(run_node())

        if len(message_group) == 1:
            loop = asyncio.get_event_loop()
            loop.call_later(node.group_messages_timeout, run_sync)
            self.log.info(
                f"Created task for group message [room: {room.room_id}] [node: {node.id}] in {node.group_messages_timeout} seconds"
            )

    def publish_event(self, message: MessageEvent, room_id: RoomID | None = None):
        if self.ROOM_STATUS[room_id].queue_message is None:
            self.log.warning(f"[{room_id}] Doesn't have a message queue")
            return

        queue = self.ROOM_STATUS[room_id].queue_message
        queue.put_nowait(message)
        self.log.info(f"[{room_id}] Message ({message.event_id}) published")

        return queue

    async def wait_for_messages(self, room: Room) -> MessageEvent:
        room_id = room.room_id
        queue = self.ROOM_STATUS[room_id].queue_message

        if queue is None:
            self.log.warning(f"[{room_id}] Doesn't have a message queue. Creating one")
            queue = self.ROOM_STATUS[room_id].queue_message = asyncio.Queue()

        self.log.info(f"[{room_id}] Waiting for messages...")

        message_event = await queue.get()
        # try:
        # message_event = await asyncio.wait_for(queue.get(), timeout=60)
        # except asyncio.TimeoutError:
        # self.log.warning(f"[{room_id}] Timeout waiting for messages")
        # return None
        return message_event

    async def algorithm(self, room: Room, evt: MessageEvent | None = None) -> None:
        """The algorithm function is the main function that runs the flow.
        It takes a room and an event as parameters

        Parameters
        ----------
        room : Room
            The room object.
        evt : MessageEvent | None
            The event that triggered the algorithm.
        """

        if self.ROOM_STATUS[room.room_id].lock_room is not None:
            self.log.warning(f"[{room.room_id}] Algorithm already running skipping...")
            return

        self.ROOM_STATUS[room.room_id].lock_room = True

        while (node := self.flow.node(room=room)) and room.route.state != RouteState.END:
            self.log.debug(
                f"[{room.room_id}] Executing node: [{node.id}]. "
                f"State: ({room.route.state}). "
                f"Triggered by: ({evt.event_id if getattr(evt, 'event_id', None) else 'unknown'}). "
                f"Sender: ({evt.sender if getattr(evt, 'sender', None) else 'unknown'}). "
                f"Timestamp: ({evt.timestamp if getattr(evt, 'timestamp', None) else 'unknown'}). "
                f"Type evt: ({type(evt)}). "
            )

            try:
                if type(node) in (Input, InteractiveInput, FormInput, GPTAssistant, Webhook):
                    await node.run(evt)
                    if room.route.state == RouteState.INPUT:
                        self.ROOM_STATUS[room.room_id].lock_room = False
                        evt = await self.wait_for_messages(room=room)
                        self.log.info(f"[{room.room_id}] Message received in algorithm")
                else:
                    await node.run()
                    if room.route.state == RouteState.INVITE:
                        # TODO: Review this logic
                        self.log.debug(
                            f"[{room.room_id}] Invite state detected. Breaking out of the loop"
                        )
                        break
            except MLimitExceeded as e:
                self.log.error(
                    f"[{room.room_id}] MLimitExceeded exception has occurred in the pipeline [{node.id}]: {e}\n"
                    f"please check your flow configuration to prevent this."
                )
            except Exception as e:
                self.log.exception(
                    f"[{room.room_id}] Exception has occurred in the algorithm: \n{e}"
                )
                room.route.state = RouteState.ERROR
                break

        if room.route.state in (RouteState.ERROR, RouteState.END) or node is None:
            if node is None:
                msg = "Does not have a valid node"
            elif room.route.state == RouteState.ERROR:
                msg = f"Has encountered an error in node {node.id}"
            elif room.route.state == RouteState.END:
                msg = "Has terminated the flow"

            self.log.info(f"[{room.room_id}] {msg}. Updating to start")
            await room.update_menu(node_id="start")

        self.ROOM_STATUS[room.room_id].queue_message = self.ROOM_STATUS[room.room_id].lock_room = (
            None
        )

    async def create_inactivity_tasks(self) -> None:
        """This function creates tasks for rooms that are in the input state
        and in an inactive state after the last system reboot."""

        inactivity_rooms: list[DBRoom] = await DBRoom.get_node_var_by_state(
            state=RouteState.INPUT.value, variable_name="inactivity", menuflow_bot_mxid=self.mxid
        )

        recreate_rooms = []
        for inactivity_room in inactivity_rooms:
            room: Room = await Room.get_by_room_id(
                room_id=inactivity_room.get("room_id"), bot_mxid=self.mxid
            )

            task_name = f"inactivity_restored_{room.room_id}"
            if room and not Util.get_tasks_by_name(task_name):
                self.log.warning(
                    f"Recreating inactivity task for room: {room.room_id} in {self.mxid}"
                )

                self.lock_room(room_id=room.room_id)
                if room.matrix_client is None:
                    room.matrix_client = self

                node = self.flow.node(room=room)
                if node is None:
                    self.log.warning(
                        f"Node was not found for room: {room.room_id} in {self.mxid} and will be updated to start"
                    )
                    await room.update_menu(node_id=RouteState.START)
                    continue

                inactivity = node.inactivity_options
                if inactivity.get("active"):
                    self.log.warning(f"[{room.room_id}] Creating inactivity task ({task_name})")
                    task = asyncio.create_task(
                        node.timeout_active_chats(inactivity), name=task_name
                    )
                    task.metadata = {"bot_mxid": self.mxid}
                    task.created_at = datetime.now(timezone.utc).timestamp()
                    # This ensures that the algorithm runs after the inactivity_options task completes.
                    task.add_done_callback(
                        lambda _task, _room=room: asyncio.ensure_future(self.algorithm(room=_room))
                    )  # _task is required because add_done_callback always passes the completed task as the first argument.
                    recreate_rooms.append(room.room_id)

        if recreate_rooms:
            self.log.info(
                f"[{len(recreate_rooms)} rooms] inactivity_option tasks that were in progress have been recreated in {self.mxid}"
                f" {recreate_rooms=}"
            )
