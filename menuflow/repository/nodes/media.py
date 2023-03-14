from __future__ import annotations

from typing import Any, Dict

from attr import dataclass, ib

from .message import Message


@dataclass
class Media(Message):
    """
    ## File

    A message node allows a message to be sent,
    these messages can be formatted using jinja variables.

    content:

    ```
    - id: m1
      type: media
      message_type: m.image | m.audio | m.video | m.file"
      text: "Hello World!"
      url: "https://images.dog.ceo/breeds/hound-blood/n02088466_12353.jpg"
      info:
        any: any
      o_connection: m2
    ```
    """

    url: str = ib(default=None)
    info: Dict[str, Any] = ib(default=None)
