from __future__ import annotations

from typing import Any, Dict, List

from attr import dataclass, ib
from mautrix.types import Obj

from ..flow_object import FlowObject


class Variables(Obj):
    set: Dict[str, Any] = ib(default={})
    unset: List[str] = ib(default=[])


@dataclass
class SetVars(FlowObject):
    """
    ## SetVars

    A set_vars node allows you to set, update, or delete variables at the `room` and `route` scope.

    Example:

    ```
    - id: set_vars_node
      type: set_vars
      variables:
        set:
          new_variable: "John Doe"
          hard_validation: >
              {%- set random_dates = [] -%}
              {%- for n in range(5) %}
                  {%- set month = range(10, 12)|random %}
                  {%- set day = range(1, 30)|random %}
                  {%- set year = range(2023, 2024)|random %}
                  {%- set hour = range(0, 23)|random %}
                  {%- set minute = range(0, 59)|random %}
                  {%- set random_date = day ~ '/' ~ month ~ '/' ~ year ~ ' ' ~ hour ~ ':' ~ minute %}
                  {%- set _ = random_dates.append(random_date) %}
              {%- endfor -%}
              {{ random_dates }}
        unset:
          - variable_to_unset1
          - variable_to_unset2
          - variable_to_unset3
          - room.data
          - route.token
      o_connection: message2
    ```
    """

    variables: Variables = ib(default=None)
    o_connection: str = ib(default=None)
