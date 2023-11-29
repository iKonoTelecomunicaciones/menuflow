from asyncio import Future, create_task, get_running_loop, sleep
from datetime import datetime
from typing import Dict

from menuflow.room import Room

from ..db.room import RoomState
from ..repository import InviteUser as InviteUserModel
from .switch import Switch


class InviteUser(Switch):
    def __init__(
        self, invite_node_data: InviteUserModel, room: Room, default_variables: Dict
    ) -> None:
        super().__init__(invite_node_data, room, default_variables)
        self.content = invite_node_data

    @property
    def invitee(self) -> list[str]:
        return self.render_data(self.content.get("invitee"))

    @property
    def timeout(self) -> str:
        return self.render_data(self.content.get("timeout"))

    async def _update_menu(self, case_id: str):
        o_connection = await self.get_case_by_id(case_id)
        await self.room.update_menu(o_connection)
        await self.room.matrix_client.algorithm(room=self.room)

    async def run(self):
        # Invite users to a room.
        await self.room.matrix_client.invite_user(self.room.room_id, self.invitee)
        await self.room.update_menu(self.id, RoomState.INVITE)

        loop = get_running_loop()
        pending_invite = loop.create_future()
        # Save the Future object in the pending_invites dict.
        self.room.pending_invites[self.room.room_id] = pending_invite

        create_task(self.check_agent_join(pending_invite))

    async def check_agent_join(self, pending_invite: Future):
        # Check if the agent has joined the room.
        loop = get_running_loop()
        end_time = loop.time() + float(self.timeout)

        while True:
            self.log.debug(datetime.now())
            if pending_invite.done():
                # when a join event is received, the Future object is resolved
                self.log.debug("FUTURE IS DONE")
                case_id = "join" if pending_invite.result() else "reject"
                break
            elif (loop.time() + 1.0) >= end_time:
                self.log.debug("TIMEOUT COMPLETED.")
                pending_invite.set_result(False)
                # Remove user invitation from the room.
                await self.room.matrix_client.kick_user(self.room.room_id, self.invitee)
                case_id = "timeout"
                break

            await sleep(1)

        if self.room.room_id in self.room.pending_invites:
            del self.room.pending_invites[self.room.room_id]

        await self._update_menu(case_id)
