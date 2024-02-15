from __future__ import annotations

from typing import Any, Dict, Optional

from attr import dataclass, ib
from mautrix.types import SerializableAttrs

from ..flow_object import FlowObject


@dataclass
class AdditionalArguments(SerializableAttrs):
    """Aditional Arguments.

    Aditional Arguments for IRM Middleware.

    - temperature: influences the randomness of the model's output during text generation,
    it can be a float between 0 and 1.
    - top_p: can be a float between 0 and 1.
    - top_k: can be an integer.
    - max_output_tokens: is the max length of the model output, it can be an integer.
    - frequency_penalty: is a float.
    - presence_penalty: is a float.
    """

    temperature: Optional[str] = ib(default="0.4")
    top_p: Optional[str] = ib(default="0.9")
    top_k: Optional[str] = ib(default="40")
    max_output_tokens: Optional[str] = ib(default="1024")
    frequency_penalty: Optional[int] = ib(default=0)
    presence_penalty: Optional[int] = ib(default=0)


@dataclass
class LLMMiddleware(FlowObject):
    """Large language model Middleware.

    An LLMMiddleware is used to implement large language models in Menuflow.

    content:

        ```
        middlewares:
            -   id: irm_middleware
                type: irm
                method: POST
                url: "https://webapinet.userfoo.com/api/llm/generate_text"
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
    model: str = ib(default=None)
    prompt: str = ib(factory=str)
    provider: str = ib(factory=str)
    args: Dict[str, Any] = ib(factory=dict)
    additional_arguments: AdditionalArguments = ib(factory=AdditionalArguments)

    @classmethod
    def from_dict(cls, data: Dict) -> LLMMiddleware:
        return cls(
            id=data.get("id"),
            type=data.get("type"),
            method=data.get("method"),
            url=data.get("url"),
            variables=data.get("variables"),
            cookies=data.get("cookies"),
            headers=data.get("headers"),
            basic_auth=data.get("basic_auth"),
            model=data.get("model"),
            prompt=data.get("prompt"),
            provider=data.get("provider"),
            args=data.get("args"),
            additional_arguments=AdditionalArguments(**data.get("additional_arguments", {})),
        )
