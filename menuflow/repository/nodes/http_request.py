from __future__ import annotations

from typing import Any, Dict, List

from attr import dataclass, ib

from .switch import Case, Switch


@dataclass
class HTTPRequest(Switch):
    """
    ## HTTPRequest

    HTTPRequest is a subclass of Switch which allows sending a message formatted with jinja
    variables and capturing the response to transit to another node according to the validation

    content:

    ```
    - id: 'r1'
      type: 'http_request'
      method: 'GET'
      url: 'https://inshorts.deta.dev/news?category={{category}}'

      variables:
        news: data

      cases:
        - id: 200
          o_connection: m1
        - id: default
          o_connection: m2
    ```
    """

    method: str = ib(default=None)
    url: str = ib(default=None)
    middleware: str = ib(default=None)
    variables: Dict[str, Any] = ib(factory=dict)
    cookies: Dict[str, Any] = ib(factory=dict)
    query_params: Dict[str, Any] = ib(factory=dict)
    headers: Dict[str, Any] = ib(factory=dict)
    basic_auth: Dict[str, Any] = ib(factory=dict)
    data: Dict[str, Any] = ib(factory=dict)
    cases: List[Case] = ib(factory=list)
