from __future__ import annotations

from typing import Any, Dict

from attr import dataclass, ib

from .message import Message


@dataclass
class Media(Message):
    """
    ## File

    A message node allows a media message to be sent,
    these text can be formatted using jinja variables.

    content:

    ```
    - id: media1
      type: media
      message_type: m.image | m.audio | m.video | m.file"
      text: "Title multimedia information"
      url: "https://images.dog.ceo/breeds/hound-blood/n02088466_12353.jpg"
      info:
        mimetype: image/jpeg
        size: 29651
        height: 500
        width: 333
      o_connection: m2
    ```
    """

    url: str = ib(default=None)
    info: Dict[str, Any] = ib(default=None)
