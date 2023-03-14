from __future__ import annotations

from typing import List

from attr import dataclass, ib
from mautrix.types import SerializableAttrs

from .message import Message
from .switch import Case, Switch


@dataclass
class InactivityOptions(SerializableAttrs):
    chat_timeout: int = ib(default=None)
    warning_message: str = ib(default=None)
    time_between_attempts: int = ib(default=None)
    attempts: int = ib(default=None)


@dataclass
class Input(Switch, Message):
    """
    ## Input

    An input type node allows sending a message formatted with jinja variables
    and capturing the response to transit to another node according to the validation.

    content:

    ```
    - id: i1
      type: input
      text: 'Enter a number'
      variable: opt
      validation: '{{ opt.isdigit() }}'
      inactivity_options:
        chat_timeout: 20 #seconds
        warning_message: "Message"
        time_between_attempts: 10 #seconds
        attempts: 3
      cases:
        - id: true
            o_connection: m1
        - id: false
            o_connection: m2
        - id: default
            o_connection: m3
    ```
    """

    variable: str = ib(default=None)
    cases: List[Case] = ib(factory=list)
    inactivity_options: InactivityOptions = ib(default=None)
