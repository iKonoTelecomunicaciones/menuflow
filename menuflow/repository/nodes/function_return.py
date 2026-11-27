from __future__ import annotations

from typing import Any

from attr import dataclass, ib

from ..flow_object import FlowObject


@dataclass
class FunctionReturn(FlowObject):
    """
    ## FunctionReturn

    Explicit return: closes the active frame with ``value`` and jumps to the
    caller (``function_call``), which routes through case ``return``.

    content:

    ```
    - id: fn_return_ok
      type: function_return
      value:
        customer: "{{ route.customer }}"
        invoices: "{{ route.invoices }}"
    ```
    """

    value: Any = ib(default=None)
