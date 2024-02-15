from __future__ import annotations

from typing import Any, Dict

from attr import dataclass, ib

from ..flow_object import FlowObject


@dataclass
class TTMMiddleware(FlowObject):
    """Text translation model Middleware.

    An TTMMiddleware is used to translate text from a source language to a target language.

    content:

        ```
        middlewares:
            -   id: irm_middleware
                type: irm
                method: POST
                url: "https://webapinet.userfoo.com/api/irm/recognize"
                prompt: "Given an image, give me the text in it"
                variables:
                    token: token
                headers:
                    Client-token: "example-token"

    """

    method: str = ib(default=None)
    url: str = ib(default=None)
    variables: Dict[str, Any] = ib(factory=dict)
    cookies: Dict[str, Any] = ib(factory=dict)
    headers: Dict[str, Any] = ib(factory=dict)
    basic_auth: Dict[str, Any] = ib(factory=dict)
    target_language: str = ib(factory=str)
    source_language: str = ib(factory=str)
    provider: str = ib(factory=str)
