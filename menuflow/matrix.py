from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from mautrix.client import Client as MatrixClient
from mautrix.errors.request import MLimitExceeded
from mautrix.types import (
    EventType,
    Membership,
    MemberStateEventContent,
    MessageEvent,
    MessageType,
    RelationType,
    RoomID,
    StateEvent,
    StateUnsigned,
    StrippedStateEvent,
    UserID,
)

from .config import Config
from .db.room import Room as DBRoom
from .db.route import RouteState
from .nodes import Base, FormInput, GPTAssistant, Input, InteractiveInput, Webhook
from .repository.room_status import RoomStatus
from .room import Room
from .user import User
from .utils import Util

if TYPE_CHECKING:
    from .flow import Flow, Node
    from .repository import FlowUtils


class MatrixHandler(MatrixClient):
    def __init__(
        self, config: Config, flow: Flow, flow_utils: FlowUtils | None = None, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.config = config
        self.flow_utils = flow_utils
        self.util = Util(self.config)
        self.flow = flow
        self.LOCKED_ROOMS = set()
        self.LAST_JOIN_EVENT: dict[RoomID, StrippedStateEvent] = {}
        self.QUEUE_MESSAGE: dict[RoomID, asyncio.Queue] = {}
        Base.init_cls(config=self.config, session=self.api.session)

    def handle_sync(self, data: dict) -> list[asyncio.Task]:
        # This is a way to remove duplicate events from the sync
        try:
            rooms = data.get("rooms", {}).get("join", {})
            for room_id, room_data in rooms.items():
                last_join_evt = self.LAST_JOIN_EVENT.get(room_id, {})
                events = room_data.get("timeline", {}).get("events", [])
                for evt in events:
                    if (
                        evt.get("type", "") == "m.room.member"
                        and evt.get("state_key", "") == self.mxid
                        and evt.get("content", {}).get("membership") == "join"
                        and evt.get("origin_server_ts") > last_join_evt.get("origin_server_ts", 0)
                    ):
                        last_join_evt = self.LAST_JOIN_EVENT[room_id] = evt

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
            f"[{room_id}] Unlocking room for event ({evt.event_id if isinstance(evt, StrippedStateEvent) else 'unknown'})"
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
        room: Room = await Room.get_by_room_id(
            room_id=evt.room_id, bot_mxid=self.mxid, create=False
        )
        if not room:
            self.log.warning(f"[{evt.room_id}] Room not found. Ignoring leave event")
            return
        room.room_status = RoomStatus.deserialize(room._status)

        if getattr(evt, "timestamp", 0) < room.room_status.last_join_ts:
            self.log.warning(
                f"[{evt.room_id}] Ignoring {evt.content.get('membership')} event ({evt.event_id}) "
                f"is older than last join event ({room.room_status.last_join_event.get('event_id')})"
            )
        else:
            self.log.info(
                f"[{evt.room_id}] Handling leave event ({evt.event_id}) for bot ({evt.state_key})"
            )
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

    async def update_room_status(self, room: Room, evt: StateEvent | MessageEvent):
        """This function updates the room status in the database.

        Parameters
        ----------
        room : Room
            The room object.
        evt : StateEvent | MessageEvent
            The event that triggered the update.
        """
        if evt.type == EventType.ROOM_MEMBER:
            room.room_status.last_join_event = evt
            msg = f"Updating join event ({evt.event_id}) in db from cache"
        elif evt.type == EventType.ROOM_MESSAGE:
            room.room_status.last_processed_message = evt
            msg = f"Updating message event ({evt.event_id}) in db from cache"
        else:
            self.log.warning(f"[{room.room_id}] Invalid event type: {evt.type.t}. Ignoring...")
            return

        room.status = room.room_status.serialize()
        await room.update_status()
        self.log.info(f"[{room.room_id}] {msg}")

    async def handle_join(self, evt: StateEvent):
        membership_evt = evt.content.get("membership")
        base_msg = f"[{evt.room_id}] Ignoring {membership_evt} event ({evt.event_id})."

        if evt.room_id in Room.pending_invites and not Room.pending_invites[evt.room_id].done():
            Room.pending_invites[evt.room_id].set_result(True)

        locked = evt.room_id in self.LOCKED_ROOMS
        if locked or not evt.state_key == self.mxid:
            self.log.warning(f"{base_msg} {"Menu locked." if locked else "Not from the bot"}")
            return

        room: Room = await Room.get_by_room_id(room_id=evt.room_id, bot_mxid=self.mxid)
        room.room_status = RoomStatus.deserialize(room._status)
        last_join_evt = room.room_status.last_join_event

        if getattr(evt, "timestamp", 0) < room.room_status.last_join_ts:
            self.log.warning(
                f"{base_msg} Is older than last join event ({last_join_evt.event_id})"
            )
            return

        if last_join_evt and evt.event_id == last_join_evt.get("event_id"):
            self.log.warning(f"{base_msg} Already processed.")
            return

        self.log.info(f"[{evt.room_id}] Join event ({evt.event_id}) from {evt.state_key} accepted")

        room.config = self.config
        room.matrix_client = self

        # Clean up the actions
        await room.clean_up()
        if (room.room_id, room.route.id) in GPTAssistant.assistant_cache:
            del GPTAssistant.assistant_cache[(room.room_id, room.route.id)]

        await self.load_room_constants(evt.room_id)
        await self.update_room_status(room=room, evt=evt)
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
        room.room_status = RoomStatus.deserialize(room._status)

        last_message_time = datetime.fromtimestamp(room.room_status.last_message_ts / 1000)
        current_message_time = datetime.fromtimestamp(message.timestamp / 1000)

        if last_message_time > current_message_time:
            self.log.warning(
                f"[{message.room_id}] Ignoring message because it's older than the last processed message"
            )
            return

        if (
            last_message_time
            and (current_message_time - last_message_time).seconds
            < self.config["menuflow.message_rate_limit"]
            and not self.flow.get_node_by_id(node_id=room.route.node_id).get("type")
            == "gpt_assistant"
        ):
            self.log.warning(f"[{message.room_id}] Message ignored due to rate limit")
            return

        room.config = self.config = self.config
        room.matrix_client = self

        # TODO: Review this logic to ignore messages in pending invites.
        if room.room_id in Room.pending_invites:
            self.log.warning(f"[{room.room_id}] Ignoring message in pending invite")
            return

        queue = None

        if self.config["menuflow.enqueue_messages"] or room.route.state == RouteState.INPUT:
            queue = await self.enqueue_message(message=message, room=room)

        # TODO: Review this logic
        if not queue:
            await self.algorithm(room=room, evt=message)

    async def enqueue_message(self, message: MessageEvent, room: Room) -> asyncio.Queue | None:
        """Enqueues a message associated with a room and updates the room status.

        Parameters
        ----------
        message : MessageEvent
            The message event object.
        room : Room
            The room object.

        Returns
        -------
        queue : asyncio.Queue | None
            The queue object if it exists, otherwise None.
        """
        queue = self.QUEUE_MESSAGE.get(room.room_id)

        if queue is None:
            self.log.warning(f"[{room.room_id}] Doesn't have a message queue")
            return None

        queue.put_nowait(message)
        self.log.info(f"[{room.room_id}] Message ({message.event_id}) enqueued")
        await self.update_room_status(room=room, evt=message)

        return queue

    async def get_input_response(self, room: Room, node: Node) -> list[MessageEvent] | None:
        """Waits for the next message(s) from the room, applying inactivity and grouping settings.

        Parameters
        ----------
        room : Room
            The room object.
        node : Node
            The node object.

        Returns
        -------
        message_list : list[MessageEvent] | None
            The list of message events or None if the timeout is reached.
        """
        room_id = room.room_id
        message_list: list[MessageEvent] = []
        queue = self.QUEUE_MESSAGE.setdefault(room_id, asyncio.Queue())

        inactivity = getattr(node, "inactivity_options", {})
        is_active = inactivity.get("active", False)
        chat_timeout = inactivity.get("chat_timeout", 0)

        use_inactivity = is_active and not (isinstance(node, Webhook) and chat_timeout <= 0)

        if use_inactivity:
            self.log.info(f"[{room_id}] Waiting for messages...")
            msg = await self.process_inactivity_options(
                room=room, inactivity=inactivity, queue=queue
            )

            room.set_node_var(inactivity={})
            await room.route.update()

            if room.route.state == RouteState.TIMEOUT:
                return message_list

            message_list.append(msg)
        else:
            self.log.info(f"[{room_id}] Inactivity options not detected")
            return None

        if timeout := getattr(node, "group_messages_timeout", 0):
            # Grouping messages until the timeout is reached or the queue is empty.
            while (
                msg := await self.wait_for_queue_item(queue=queue, timeout=timeout)
            ) is not None:
                self.log.info(
                    f"[{room_id}] Grouping messages enabled. "
                    f"Message received, waiting ({timeout} seconds) for next message..."
                )
                message_list.append(msg)
        return message_list

    async def algorithm(
        self, room: Room, evt: MessageEvent | None = None, run_input_node: bool = True
    ) -> None:
        """The algorithm function is the main function that runs the flow.
        It takes a room and an event as parameters

        Parameters
        ----------
        room : Room
            The room object.
        evt : MessageEvent | None
            The event that triggered the algorithm.
        run_input_node : bool, optional
            If True (default), the current input-like node is executed.
            If False, the execution of the input node is skipped only on the
            first iteration of this call (used when resuming from
            `create_inactivity_tasks` so the same message is not processed
            again); from the next iteration onward the flag is treated as True.

        """
        room_locked = room.room_id in self.LOCKED_ROOMS
        if room_locked and run_input_node:
            self.log.warning(f"[{room.room_id}] Algorithm already running skipping...")
            return

        if not room_locked:
            self.lock_room(room_id=room.room_id, evt=evt)

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
                    if run_input_node:
                        await node.run(evt)
                    run_input_node = True  # one-time reset to True
                    if room.route.state == RouteState.INPUT:
                        evt = await self.get_input_response(room=room, node=node)
                        if evt is None:
                            self.log.info(
                                f"[{room.room_id}] Stopping the flow until a new message arrives"
                            )
                            break

                        if evt:
                            _msg = f"{len(evt)} message(s) received in algorithm"

                            # TODO: Review this logic when all input nodes can receive a list of messages.
                            if not isinstance(node, GPTAssistant):
                                evt = evt[0]
                        else:
                            _msg = "No messages received in algorithm. Continuing with the flow"
                        self.log.info(f"[{room.room_id}] {_msg}")
                else:
                    await node.run()
                    if room.route.state == RouteState.INVITE:
                        self.log.debug(
                            f"[{room.room_id}] Invite state detected. Breaking out of the loop"
                        )
                        break
            except MLimitExceeded as e:
                self.log.error(
                    f"[{room.room_id}] MLimitExceeded exception has occurred in the pipeline [{node.id}]: {e}\n"
                    f"please check your flow configuration to prevent this."
                )
                break
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

        self.QUEUE_MESSAGE.pop(room.room_id, None)
        self.unlock_room(room_id=room.room_id, evt=evt)

    async def create_inactivity_tasks(self) -> None:
        """This function creates tasks for rooms that are in the input state
        and in an inactive state after the last system reboot or flow save."""

        inactivity_rooms: list[DBRoom] = await DBRoom.get_node_var_by_state(
            state=RouteState.INPUT.value, variable_name="inactivity", menuflow_bot_mxid=self.mxid
        )

        recreate_rooms = []
        for inactivity_room in inactivity_rooms:
            room: Room = await Room.get_by_room_id(
                room_id=inactivity_room.get("room_id"), bot_mxid=self.mxid
            )
            room.room_status = RoomStatus.deserialize(room._status)

            task_name = room.room_id
            if room and not Util.get_tasks_by_name(task_name):
                self.log.warning(f"[{room.room_id}] Reloading inactivity options")

                if room.matrix_client is None:
                    room.matrix_client = self

                task = asyncio.create_task(
                    self.algorithm(
                        room=room,
                        evt=room.room_status.last_processed_message,
                        run_input_node=False,
                    ),
                    name=task_name,
                )
                task.bot_mxid = self.mxid
                task.created_at = datetime.now(timezone.utc).timestamp()
                recreate_rooms.append(room.room_id)

                task.add_done_callback(
                    lambda _task, _room=room: self._on_inactivity_done(_task, _room)
                )  # _task is required because add_done_callback always passes the completed task as the first argument.

        if recreate_rooms:
            self.log.info(
                f"[{len(recreate_rooms)} rooms] inactivity_option tasks that were in progress "
                f"have been recreated in {self.mxid} {recreate_rooms=}"
            )

    async def process_inactivity_options(
        self, room: Room, inactivity: dict, queue: asyncio.Queue
    ) -> MessageEvent | None:
        """Execute the node's idle policy until the timeout is reached,
        the maximum number of attempts is reached, or a new event enters the queue.

        Parameters
        ----------
        room : Room
            The room object.
        inactivity : dict
            The inactivity options.
        queue : asyncio.Queue
            The queue object.

        Returns
        -------
        MessageEvent | None
            The message event object or None.
        """
        chat_timeout = inactivity.get("chat_timeout", 0) or 0
        attempts = inactivity.get("attempts", 0) or 0

        if chat_timeout is None and attempts is None:
            return

        self.log.info(f"[{room.room_id}] Processing inactivity options...")

        inactivity_db: dict = room.route._node_vars.setdefault("inactivity", {})
        for key in ("attempt", "start_ttl", "attempt_ttl"):
            inactivity_db.setdefault(key, 0)

        warning_message = inactivity.get("warning_message", "")
        time_between_attempts = inactivity.get("time_between_attempts", 0) or 0

        if inactivity_db["attempt"] == 0:
            now = datetime.now().timestamp()
            if inactivity_db.get("start_ttl") == 0:
                inactivity_db["start_ttl"] = now + chat_timeout
                room.set_node_var(inactivity=inactivity_db)
                await room.route.update_node_vars()

            start_sleep = inactivity_db["start_ttl"] - now
            if start_sleep > 0:
                self.log.info(
                    f"[{room.room_id}] Start chat timeout, sleeping {start_sleep} seconds"
                )

                msg = await self.wait_for_queue_item(queue=queue, timeout=start_sleep)
                if msg is not None:
                    return msg

        while True:
            attempt = inactivity_db["attempt"]
            attempt_ttl = inactivity_db.get("attempt_ttl")
            now = datetime.now().timestamp()

            if (attempt == attempts and attempt_ttl - now < 0) or attempt > attempts:
                break

            if attempt_ttl - now < 0:
                inactivity_db["attempt_ttl"] = now + time_between_attempts
                inactivity_db["attempt"] += 1
                room.set_node_var(inactivity=inactivity_db)
                await room.route.update_node_vars()

                if warning_message:
                    await room.matrix_client.send_text(room_id=room.room_id, text=warning_message)

            attempt_sleep = inactivity_db["attempt_ttl"] - now
            self.log.info(
                f"[{room.room_id}] Inactivity Attempts {inactivity_db['attempt']} of "
                f"{attempts} sleeping ({attempt_sleep} seconds)"
            )

            msg = await self.wait_for_queue_item(queue=queue, timeout=attempt_sleep)
            if msg is not None:
                return msg

        self.log.warning(f"[{room.room_id}] INACTIVITY TRIES COMPLETED...")
        room.route.state = RouteState.TIMEOUT

    async def wait_for_queue_item(self, queue: asyncio.Queue, timeout: int):
        """Wait for the next item in the queue until the time limit expires.

        Parameters
        ----------
        queue : asyncio.Queue
            The asynchronous queue from which the message is retrieved (consumed with `queue.get()`).
        timeout : int
            The maximum waiting time in seconds. If it is 0 or negative, it immediately returns `None`.

        Returns:
            The message retrieved from the queue if it arrives before the `timeout`; otherwise, `None`.
        """
        if timeout <= 0:
            return None

        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def _on_inactivity_done(self, task: asyncio.Task, room: Room) -> None:
        """Callback function for the inactivity task.
        It is used to handle the cancellation of the inactivity task.

        Parameters
        ----------
        task : asyncio.Task
            The task object.
        room : Room
            The room object.
        """
        if task.cancelled():
            self.log.warning(f"[{room.room_id}] Inactivity task was cancelled")
            return
