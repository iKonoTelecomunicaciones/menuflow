from __future__ import annotations

from typing import Any, Dict

from attr import dataclass, ib

from ..flow_object import FlowObject

@dataclass
class ASRMiddleware(FlowObject):
    """ASRMiddleware

    Middleware node recognize the text from a sound file.

    content:

    ```
    - id: m1
      type: asr
      method: GET
      url: "http://localhost:5000/asr"
      provider: "azure"
      cookies:
          cookie1: "value1"
      header:
          header1: "value1"
      variables:
          variable1: "value1"
    """

    id: str = ib(default=None)
    type: str = ib(default=None)
    method: str = ib(default=None)
    url: str = ib(default=None)
    provider: str = ib(default=None)
    cookies: Dict[str, Any] = ib(factory=dict)
    headers: Dict[str, Any] = ib(default=None)
    variables: Dict[str, Any] = ib(factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> ASRMiddleware:
        return cls(
            id=data.get("id"),
            type=data.get("type"),
            method=data.get("method"),
            url=data.get("url"),
            provider=data.get("provider"),
            variables=data.get("variables"),
            cookies=data.get("cookies"),
            headers=data.get("headers"),
        )