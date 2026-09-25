import asyncio
import time
from enum import Enum

from mautrix.types import UserID

from ..db.route import RouteState
from ..repository import InviteUser as InviteUserModel
from ..repository.nodes.invite_user import OnJoin
from ..room import Room
from ..room_sync_primitives import PrimitiveType, RoomSyncPrimitives
from ..utils.types import NodeStatus
from .switch import Switch


class InviteCase(Enum):
    ERROR = "error"
    JOIN = "join"
    REJECT = "reject"
    TIMEOUT = NodeStatus.TIMEOUT.value


class InviteUser(Switch):
    def __init__(
        self, invite_node_data: InviteUserModel, room: Room, default_variables: dict
    ) -> None:
        super().__init__(invite_node_data, room, default_variables)
        self.content = invite_node_data

    @property
    def invitee(self) -> UserID:
        return self.render_data(self.content.get("invitee"))

    @property
    def timeout(self) -> str:
        return self.render_data(self.content.get("timeout"))

    @property
    def leave_reason(self) -> str:
        return self.render_data(data=self.content.get("leave_reason", ""))

    @property
    def on_join(self) -> OnJoin:
        return self.render_data(self.content.get("on_join", OnJoin.LEAVE.value))

    @property
    def _is_menubot_invitee(self) -> bool:
        from ..menu import MenuClient

        return self.invitee in MenuClient.cache

    async def _route_case(self, case_id: str | InviteCase) -> None:
        """Advance the menu to the case connection without re-entering algorithm."""
        o_connection = await self.get_case_by_id(
            case_id if isinstance(case_id, str) else case_id.value
        )
        await self.room.update_menu(o_connection)

    async def _invite_and_wait(
        self, room_id, user_id: UserID, timeout: float, invite_ack
    ) -> InviteCase:
        """Invite and wait for JOIN/REJECT/ERROR. Returns ERROR if already routed (reject/timeout)."""
        try:
            await self.room.matrix_client.invite_user(room_id, user_id)
        except Exception as e:
            self.log.error(f"[{room_id}] User {user_id} not invited: {e}")
            return InviteCase.ERROR

        try:
            # shield keeps the Future usable if wait_for times out
            return await asyncio.wait_for(asyncio.shield(invite_ack), timeout=timeout)
        except asyncio.TimeoutError:
            self.log.warning(f"[{room_id}] Timeout waiting for invitee {user_id} to join")
            try:
                await self.room.matrix_client.kick_user(room_id, user_id)
            except Exception as e:
                self.log.error(f"[{room_id}] Failed to kick {user_id} on timeout: {e}")
            return InviteCase.TIMEOUT

    async def _ensure_join(self, room_id, user_id: UserID, timeout: float, invite_ack) -> bool:
        """Invite and wait. True only if the result is JOIN.
        Reject and timeout already routed by _invite_and_wait.
        """
        case_id = await self._invite_and_wait(room_id, user_id, timeout, invite_ack)

        if case_id != InviteCase.JOIN:
            self.log.debug(f"[{room_id}] Invitee {user_id} result: {case_id.value}")
            await self._route_case(case_id)
            return False

        return True

    async def run(self):
        _room_id, _user_id, _timeout = self.room.room_id, self.invitee, float(self.timeout)
        self.log.debug(f"[{_room_id}] Entering invite user node {self.id}")

        should_leave = self.on_join == OnJoin.LEAVE.value or self._is_menubot_invitee
        self.log.info(
            f"[{_room_id}] Invite {_user_id} (on_join={self.on_join}, "
            f"leave={should_leave}, timeout={_timeout}s)..."
        )

        # Future for invite result keyed by invitee mxid so handle_join verifies the right user joined
        async with RoomSyncPrimitives(
            room_id=_room_id, primitive=PrimitiveType.INVITE_ACK, user_id=_user_id
        ) as invite_ack:
            invite_ack.invite_created_at = time.time()
            if should_leave:
                async with RoomSyncPrimitives(
                    room_id=_room_id, primitive=PrimitiveType.INVITE_DONE
                ) as invite_done:
                    if not await self._ensure_join(_room_id, _user_id, _timeout, invite_ack):
                        return

                    self.log.info(f"[{_room_id}] Invitee {_user_id} joined, leaving current menu.")

                    async with RoomSyncPrimitives(
                        room_id=_room_id, primitive=PrimitiveType.LEAVE_DONE
                    ) as leave_done:

                        try:
                            await self.room.matrix_client.leave_room(_room_id, self.leave_reason)
                        except Exception as e:
                            self.log.error(f"[{_room_id}] Failed to leave room: {e}")
                            return

                        try:
                            await asyncio.wait_for(leave_done.wait(), timeout=_timeout)
                        except asyncio.TimeoutError:
                            self.log.warning(f"[{_room_id}] Timeout waiting for leave to complete")
                            await self._route_case(InviteCase.TIMEOUT)
                            return

                    await self.room.update_menu(node_id=None, state=RouteState.END)

                    await self.room.matrix_client.handle_algorithm_completion(
                        room=self.room, node=self, evt=None
                    )
                    self.log.info(
                        f"[{_room_id}] Invite ended for invitee {_user_id}, "
                        "sending INVITE_DONE signal to JOIN event handler"
                    )
                    invite_done.set()
                    return RouteState.INVITE

            # Agent + next_node: wait for join, then continue flow without leaving
            if not await self._ensure_join(_room_id, _user_id, _timeout, invite_ack):
                return

            self.log.info(f"[{_room_id}] Invitee {_user_id} joined, continuing flow (next_node)")
            await self._route_case(InviteCase.JOIN)
