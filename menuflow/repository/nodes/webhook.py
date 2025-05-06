from __future__ import annotations
from typing import Any

from attr import dataclass, ib
from .input import InactivityOptions, Input

@dataclass
class Webhook(Input):
    """
    ## Webhook

    Webhook node allow the user to send a http request to a Webhook URL and capture the response
    and depending on the filter that the user set (It could be a jinja and jq filter),
    the flow will continue to the next node. Also it allows to set a timeout for the request or a
    cancel options to cancel the request if the user send a message.

    Example: webhook-1
    content:

    ```
    - id: webhook-1
      type: webhook
      validation: '{{ opt }}'

      validation_fail:
        message: "Please enter a valid option"

      filter: '.id == "{{ route.id }}"'

      inactivity_options:
        chat_timeout: 20 #seconds

      variables:
        news: data

      cases:
      - id: webhook
        o_connection: m_webhook
        variables:
          route.foo: "bar"
      - id: timeout
        o_connection: m_timeout
      - case: '{% if ( route.opt | regex_search("^[cC]ancelar(\ |$)")) ) %}True{% else %}False{% endif %}'
        o_connection: m_cancel
    ```
    """

    filter: str = ib(default=None)
    variables: dict[str, Any] = ib(factory=dict)
    inactivity_options: InactivityOptions = ib(default=None)