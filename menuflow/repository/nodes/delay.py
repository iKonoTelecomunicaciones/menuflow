from __future__ import annotations

from attr import dataclass, ib

from ..flow_object import FlowObject


@dataclass
class Delay(FlowObject):
    """
    ## Delay
    Delay the time (in seconds).

    - id: delay1
      type: delay
      time: 10 # seconds
      o_connection: m2
    """

    time: int = ib(default=None)
    o_connection: str = ib(default=None)
