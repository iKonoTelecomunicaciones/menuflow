from typing import Any, Dict, List

from attr import dataclass, ib
from mautrix.types import SerializableAttrs

from .flow_object import FlowObject


@dataclass
class Case(SerializableAttrs):
    id: str = ib()
    variables: Dict[str, Any] = ib(factory=dict)
    o_connection: str = ib(default=None)


@dataclass
class Switch(FlowObject):
    """
    ## Switch

    A switch type node allows to validate the content of a jinja variable,
    and from the result to transit to another node.

    content:

    ```
    - id: switch-1
      type: switch
      validation: '{{ opt }}'
      cases:
      - id: 1
        o_connection: m1
      - id: 2
        o_connection: m2
      - id: default
        o_connection: m3
    ```
    """

    validation: str = ib(default=None)
    cases: List[Case] = ib(factory=list)
