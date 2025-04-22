from __future__ import annotations

from attr import dataclass, ib

from .switch import Case, Switch


@dataclass
class CheckHoliday(Switch):
    """
    ## CheckHoliday

    If the current day is a holiday, it branches to the case `True` otherwise it branches to
    the case `False`.

    content:

    ```
    - id: "check_holiday_node"
      type: check_holiday
      timezone: "America/Bogota"
      country_code: "CO"
      subdivision_code: ""
      cases:
          - id: "True"
          o_connection: "message_1"
          - id: "False"
          o_connection: "message_2"
    ```
    """

    timezone: str = ib(factory=str)
    country_code: str = ib(factory=str)
    subdivision_code: str = ib(factory=str)
    cases: list[Case] = ib(factory=list)
