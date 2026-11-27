from __future__ import annotations

from typing import Any

from attr import dataclass, ib

from .switch import Switch


@dataclass
class FunctionCall(Switch):
    """
    ## FunctionCall

    Invokes a ``function`` by name (fallback to node id). On completion exposes
    ``node.function = {result, error, call_id}`` and routes via cases
    (``return`` / ``error`` / ``default``). Case variables can read the
    envelope, e.g. ``{{ node.function.error.message }}``.

    content:

    ```
    - id: call_customer
      type: function_call
      function: get_customer

      args:
        document: "{{ route.document }}"
        include_invoices: true

      variables:
        route.customer: .
        route.customer_name: .customer.name

      cases:
        - id: return
          o_connection: m_show_customer
        - id: error
          o_connection: m_error
          variables:
            route.error_msg: "{{ node.function.error.message }}"
        - id: default
          o_connection: m_fallback
    ```
    """

    function: str = ib(default=None)
    args: dict[str, Any] = ib(factory=dict)
    variables: dict[str, Any] = ib(factory=dict)
    o_connection: str = ib(default=None)
