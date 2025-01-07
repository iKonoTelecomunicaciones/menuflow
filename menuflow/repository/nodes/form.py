from __future__ import annotations

from typing import Dict

from attr import dataclass, ib
from mautrix.types import BaseMessageEventContent, SerializableAttrs

from ..flow_object import FlowObject


@dataclass
class FormMessage(SerializableAttrs, BaseMessageEventContent):
    msgtype: str = ib(default=None, metadata={"json": "msgtype"})
    body: str = ib(default="", metadata={"json": "body"})
    form_message: FormMessageContent = ib(factory=Dict, metadata={"json": "form_message"})


@dataclass
class FormMessageContent(SerializableAttrs):
    template_name: str = ib(default=None)
    language: str = ib(default=None)


@dataclass
class InactivityOptions(SerializableAttrs):
    chat_timeout: int = ib(default=None)
    warning_message: str = ib(default=None)
    time_between_attempts: int = ib(default=None)
    attempts: int = ib(default=None)


@dataclass
class Form(FlowObject):
    """
    ## Form

    Form node is a special type of input node that allows send a WhatsApp flow and
    capture the response of it and save it as variables.

    content:

    ```
    - id: f1
      type: form
      template_name: 'template_name'
      language: en
      variable: opt
      inactivity_options:
        chat_timeout: 20 #seconds
        warning_message: "Message"
        time_between_attempts: 10 #seconds
        attempts: 3
      o_connection: o1
    ```
    """

    template_name: str
    language: str
    variable: str = ib(default=None)
    inactivity_options: InactivityOptions = ib(default=None)
    o_connection: str = ib(default=None)
