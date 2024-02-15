from __future__ import annotations

from typing import Any, Dict

from attr import dataclass, ib

from ..flow_object import FlowObject


@dataclass
class ASRMiddleware(FlowObject):
    """Automatic speech recognition middleware

    Middleware node recognize the text from a sound file.

    content:

    ```
    - id: m1
      type: asr
      method: GET
      url: "http://localhost:5000/asr"
      provider: "azure"
      source_language: "es-MX"
      target_languages: "en, fr"
      cookies:
          cookie1: "value1"
      header:
          Client-token: "client-token"
      variables:
          variable1: "value1"
    """

    id: str = ib(default=None)
    type: str = ib(default=None)
    method: str = ib(default=None)
    url: str = ib(default=None)
    provider: str = ib(default=None)
    source_language: str = ib(default=None)
    target_languages: str = ib(default=None)
    cookies: Dict[str, Any] = ib(factory=dict)
    headers: Dict[str, Any] = ib(default=None)
    variables: Dict[str, Any] = ib(factory=dict)
