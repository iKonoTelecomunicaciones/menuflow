from __future__ import annotations

from typing import Any

from attr import dataclass, ib
from mautrix.types import SerializableAttrs

from ..flow_object import FlowObject


@dataclass
class FunctionParam(SerializableAttrs):
    type: str = ib(default=None)
    required: bool = ib(default=False)
    default: Any = ib(default=None)


@dataclass
class FunctionReturns(SerializableAttrs):
    type: str = ib(default=None)
    description: str = ib(default=None)
    value: Any = ib(default=None)


@dataclass
class Function(FlowObject):
    """
    ## Function

    Definition entry for a reusable function. At runtime the node checks that
    the active frame belongs to this function and jumps to ``o_connection``
    (the body). Argument validation happens in ``function_call`` before the
    frame is pushed. ``returns.value`` is used on implicit return (empty
    ``o_connection`` / ``finish`` inside the body).

    content:

    ```
    - id: fn_get_customer
      type: function
      name: get_customer
      description: "Consulta los datos de un cliente a partir de su documento"

      params:
        document:
          type: string
          required: true
        include_invoices:
          type: boolean
          default: false

      returns:
        type: object
        description: "Registro del cliente"
        value: null

      isolate: false
      o_connection: fn_http_customer
    ```
    """

    name: str = ib(default=None)
    description: str = ib(default=None)
    params: dict[str, FunctionParam] = ib(factory=dict)
    returns: FunctionReturns = ib(default=None)
    isolate: bool = ib(default=False)
    o_connection: str = ib(default=None)
