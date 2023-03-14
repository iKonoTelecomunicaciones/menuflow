from __future__ import annotations

from typing import List

from attr import dataclass, ib

from .switch import Case, Switch


@dataclass
class CheckTime(Switch):
    """
    ## CheckTime

    If the current time matches the specified time, it branches to the case `True`.
    Each of the elements can be specified as '*' (forever) or as a range.
    If the current time does not match the specified time the output will be set using case `False`.

    content:

    ```
    - id: "check_time_node"
      type: check_time
      timezone: "America/Bogota"
      time_ranges:
          - "08:00-12:00"
          - "13:00-18:00"
      days_of_week:
          - "mon-fri"
      days_of_month:
          - "8-12"
          - "6-6"
      months:
          - "*"
      cases:
          - id: "True"
          o_connection: "message_1"
          - id: "False"
          o_connection: "message_2"
    ```
    """

    time_ranges: List[str] = ib(factory=list)
    days_of_week: List[str] = ib(factory=str)
    days_of_month: List[str] = ib(factory=str)
    months: List[str] = ib(factory=str)
    timezone: str = ib(factory=str)
    cases: List[Case] = ib(factory=list)
