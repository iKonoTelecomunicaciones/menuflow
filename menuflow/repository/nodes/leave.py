from __future__ import annotations

from attr import dataclass, ib

from ..flow_object import FlowObject


@dataclass
class Leave(FlowObject):
    """
    ## Leave
    Leave the room.

    - id: leave1
      type: leave
      reason: "I'm leaving"
    """

    reason: str = ib(default=None)
