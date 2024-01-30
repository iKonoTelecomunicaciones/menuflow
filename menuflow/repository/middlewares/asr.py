from typing import Any, Dict
from mautrix.types import SerializableAttrs

from attr import dataclass, ib

from ..flow_object import FlowObject


@dataclass
class General(SerializableAttrs):
    headers: Dict[str, Any] = ib(default=None)


@dataclass
class ASRMiddlewareModel(FlowObject):
    """
    ## ASRMiddlewareModel

    A ASR middleware node allows to recognize text from a sound file.

    content:

    ```
    - id: m1
      type: asr
      method: GET
      url: "http://localhost:5000/asr"
      record_format: "wav"
      scape_digits: "#"
      timeout: 10000
      silence: 2
      cookies:
          cookie1: "value1"
      query_params:
          param1: "value1"
      general:
          header:
             header1: "value1"
      basic_auth:
          username: "user"
          password: "pass"
      data:
          data1: "value1"
      json:
          json1: "value1"
    """

    id: str = ib(default=None)
    type: str = ib(default=None)
    method: str = ib(default=None)
    url: str = ib(default=None)
    record_format: str = ib(default=None)
    scape_digits: str = ib(default=None)
    timeout: int = ib(default=None)
    silence: int = ib(default=None)
    provider: str = ib(default=None)
    cookies: Dict[str, Any] = ib(factory=dict)
    query_params: Dict[str, Any] = ib(factory=dict)
    attempts: Dict[str, Any] = ib(factory=dict)
    general: General = ib(default=None)
    basic_auth: Dict[str, Any] = ib(factory=dict)
    variables: Dict[str, Any] = ib(factory=dict)
    data: Dict[str, Any] = ib(factory=dict)
    json: Dict[str, Any] = ib(factory=dict)
    cookies: Dict[str, Any] = ib(factory=dict)
