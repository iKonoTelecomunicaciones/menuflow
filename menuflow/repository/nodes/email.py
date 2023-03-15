from __future__ import annotations

from typing import List

from attr import dataclass, ib

from .message import Message


@dataclass
class Email(Message):
    """
    ## Email

    A message node allows a message to be sent,
    these messages can be formatted using jinja variables.

    content:

    ```
    - id: m1
      type: message
      server_id: "sample-server-id"
      sender: "foo@foo.com"
      subject: The subject
      recipients:
        - foo1@foo.com
        - foo2@foo.com
        - foo2@foo.com
      text: "Hello World!"
      format: "html"
      encode_type: "utf-8"
      o_connection: m2
    ```
    """

    server_id: str = ib(default=None)
    sender: str = ib(default=None)
    subject: str = ib(default=None)
    recipients: List[str] = ib(default=None)
    format: str = ib(default=None)
    encode_type: str = ib(default=None)
