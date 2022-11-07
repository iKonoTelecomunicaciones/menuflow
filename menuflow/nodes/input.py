from __future__ import annotations

from typing import List

from attr import dataclass, ib

from .message import Message
from .switch import Case, Switch


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
      cases:
      - id: true
        o_connection: m1
      - id: false
        o_connection: m2
      - id: default
        o_connection: m3
    ```
    """

    variable: str = ib(default=None, metadata={"json": "variable"})
    cases: List[Case] = ib(metadata={"json": "cases"}, factory=list)
