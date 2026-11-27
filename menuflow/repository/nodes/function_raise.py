from __future__ import annotations

from typing import Any

from attr import dataclass, ib

from ..flow_object import FlowObject


@dataclass
class FunctionRaise(FlowObject):
    """
    ## FunctionRaise

    Explicit raise: closes the active frame with ``{code, message, data}`` and
    jumps to the caller, which routes through case ``error``.

    content:

    ```
    - id: fn_raise_not_found
      type: function_raise
      code: not_found
      message: "Cliente {{ route.document }} no encontrado"
      data:
        status: "{{ route.http_status }}"
    ```
    """

    code: str = ib(default="error")
    message: str = ib(default=None)
    data: Any = ib(default=None)
