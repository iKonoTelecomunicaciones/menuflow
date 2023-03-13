from __future__ import annotations

from attr import dataclass, ib

from ..flow_object import FlowObject


@dataclass
class Message(FlowObject):
    """
    ## Message

    A message node allows a message to be sent,
    these messages can be formatted using jinja variables.

    content:

    ```
    - id: m1
      type: message
      message_type: "m.text | m.notice"
      text: "Hello World!"
      o_connection: m2
    ```
    """

    message_type: str = ib(default=None)
    text: str = ib(default=None)
    o_connection: str = ib(default=None)
