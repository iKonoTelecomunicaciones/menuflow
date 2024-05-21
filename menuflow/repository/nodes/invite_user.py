from __future__ import annotations

from attr import dataclass, ib

from .switch import Case, Switch


@dataclass
class InviteUser(Switch):
    """
    ## Invite User
    Invite users to a room.

    - id: 'invite_user'
      type: 'invite_user'
      timeout: 5
      invitee: '{{ main_menu }}'
      cases:
        - id: 'join'
          o_connection: 'next_node'
        - id: 'reject'
          o_connection: 'error_invite_user'
        - id: 'timeout'
          o_connection: 'timeout_invite_user'
    """

    invitees: list[str] = ib(default=None)
    timeout: int = ib(default=5)
