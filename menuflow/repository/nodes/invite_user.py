from __future__ import annotations

from enum import Enum

from attr import dataclass, ib
from mautrix.types import UserID

from .switch import Switch


class OnJoin(Enum):
    LEAVE = "leave"
    NEXT_NODE = "next_node"


@dataclass
class InviteUser(Switch):
    """
    ## Invite User
    Invite users to a room.

    - id: 'invite_user'
      type: 'invite_user'
      timeout: 5
      invitee: '{{ main_menu }}'
      on_join: 'leave' | 'next_node'
      cases:
        - id: 'join'
          o_connection: 'next_node'
        - id: 'reject'
          o_connection: 'error_invite_user'
        - id: 'timeout'
          o_connection: 'timeout_invite_user'
        - id: 'fail'
          o_connection: 'fail_invite_user_api'
    """

    invitee: UserID = ib(default=None)
    timeout: int = ib(default=5)
    on_join: OnJoin = ib(default=OnJoin.LEAVE.value)
