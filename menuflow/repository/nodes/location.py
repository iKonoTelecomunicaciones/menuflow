from __future__ import annotations

from attr import dataclass, ib

from .message import Message


@dataclass
class Location(Message):
    """
    ## Location

    A location node allows a location message to be sent.

    content:

    ```
    - id: location1
      type: location
      longitude: "6.0555674"
      latitude: "46.2334715"
      o_connection: m2
    ```
    """

    longitude: str = ib(default=None)
    latitude: str = ib(default=None)
