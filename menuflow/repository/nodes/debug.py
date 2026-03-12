from __future__ import annotations

from attr import dataclass, ib

from ..flow_object import FlowObject


@dataclass
class Debug(FlowObject):
    """
    ## Debug
    Debug the msg using the debug node.

    - id: debug1
      type: debug
      level: "debug | info | warning | error | critical"
      msg: "{{ opt }}"
      o_connection: m2
    """

    level: str = ib(default=None)
    msg: str = ib(default=None)
    o_connection: str = ib(default=None)
