from __future__ import annotations

from typing import Optional

from mautrix.client import Client as MatrixClient
from mautrix.types import (
    Membership,
    MemberStateEventContent,
    MessageEvent,
    MessageType,
    RoomID,
    StateUnsigned,
    StrippedStateEvent,
)

from .config import Config
from .db.route import RouteState
from .flow import Flow
from .nodes import Base, Input, InteractiveInput
from .repository import FlowUtils
from .room import Room
from .user import User
from .utils import Util


class MatrixHandler(MatrixClient):
    def __init__(
        self, config: Config, flow_utils: Optional[FlowUtils] = None, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.config = config
        self.flow_utils = flow_utils
        self.util = Util(self.config)
        self.flow = Flow(flow_utils=flow_utils, flow_mxid=self.mxid)
        Base.init_cls(
            config=self.config,
            session=self.api.session,
        )

    async def handle_member(self, evt: StrippedStateEvent) -> None:
        unsigned = evt.unsigned or StateUnsigned()
        prev_content = unsigned.prev_content or MemberStateEventContent()
        prev_membership = prev_content.membership if prev_content else None

        if evt.state_key == self.mxid and evt.content.membership == Membership.INVITE:
            await self.handle_invite(evt)
        elif evt.content.membership == Membership.JOIN and prev_membership != Membership.JOIN:
            await self.handle_join(evt)
        elif evt.content.membership == Membership.LEAVE:
            if prev_membership == Membership.JOIN:
                await self.handle_leave(evt)
            elif prev_membership == Membership.INVITE:
                await self.handle_reject_invite(evt)

    async def handle_invite(self, evt: StrippedStateEvent):
        if self.util.ignore_user(mxid=evt.sender, origin="invite") or evt.sender == self.mxid:
            self.log.debug(f"This incoming invite event from {evt.room_id} will be ignored")
            await self.leave_room(evt.room_id)
            return

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
            await User.get_by_mxid(mxid=await room.creator)
            await room.set_variable("customer_mxid", await room.creator)

    async def handle_join(self, evt: StrippedStateEvent):
        if evt.room_id in Room.pending_invites:
            if not Room.pending_invites[evt.room_id].done():
                Room.pending_invites[evt.room_id].set_result(True)

        # Ignore all events that are not from the bot
        if not evt.state_key == self.mxid:
            return

        self.log.info(f"{evt.state_key} ACCEPTED -- EVENT JOIN ... {evt.room_id}")
        room: Room = await Room.get_by_room_id(room_id=evt.room_id, bot_mxid=self.mxid)
        room.config = self.config
        room.matrix_client = self

        await room.clean_up()

        await self.load_room_constants(evt.room_id)

        await self.algorithm(room=room)

    async def handle_leave(self, evt: StrippedStateEvent):
        pass

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

        room: Room = await Room.get_by_room_id(room_id=message.room_id, bot_mxid=self.mxid)
        room.config = self.config = self.config
        room.matrix_client = self

        if not room:
            return

        if room.room_id in Room.pending_invites:
            self.log.warning(f"Ignoring message in {room.room_id} pending invite")
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
            self.log.debug(f"Room {room.room_id} does not have a node [{node}]")
            await room.update_menu(node_id="start")
            return

        self.log.debug(f"The [room: {room.room_id}] [node: {node.id}] [state: {room.route.state}]")

        if type(node) in (Input, InteractiveInput):
            await node.run(evt=evt)
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
