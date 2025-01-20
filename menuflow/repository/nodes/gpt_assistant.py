from __future__ import annotations

from typing import List

from attr import dataclass, ib
from mautrix.types import SerializableAttrs

from .switch import Switch


@dataclass
class InactivityOptions(SerializableAttrs):
    chat_timeout: int = ib(default=None)
    warning_message: str = ib(default=None)
    time_between_attempts: int = ib(default=None)
    attempts: int = ib(default=None)


@dataclass
class GPTAssistant(Switch):
    """
    ## GptAssistant

    This node allows to interact with the GPT Assistant API.

    * If you want to create a new assistant, you need to provide name, instructions, model parameters.
    * If you want to use an existing assistant, you need to provide assistant_id.

    **Note:**
    If you want to provide the assistant some initial information,
    you can use the initial_info parameter.

    content:

    ```yaml
        - id: g1
          type: gpt_assistant
          name: "GPT Assistant"
          instructions: "Please select an option"
          model: "gpt-3.5-turbo"
          assistant_id: "123456"
          api_key: "123456"
          initial_info: "{{ route.context }}, {{ route.external.user_name }}"
          variable: opt
          validation: '{{ opt.isdigit() }}'
          validation_fail:
            message: "Please enter a valid option"
            attempts: 3
          group_messages_timeout: 10
          inactivity_options:
            chat_timeout: 20 #seconds
            warning_message: "Message"
            time_between_attempts: 10 #seconds
            attempts: 3
          cases:
            - id: true
              o_connection: m1
            - id: false
              o_connection: m2
            - id: default
              o_connection: m3
            - id: timeout
              o_connection: m4
            - id: attempt_exceeded
              o_connection: m5
    ```
    """

    name: str = ib(default=None)
    instructions: str = ib(default=None)
    model: str = ib(default=None)
    assistant_id: str = ib(default=None)
    api_key: str = ib(factory=str)
    initial_info: str = ib(default=None)
    variable: str = ib(default=None)
    validation: str = ib(default=None)
    validation_attempts: int = ib(default=None)
    inactivity_options: InactivityOptions = ib(default=None)
    middlewares: List = ib(default=None)
    group_messages_timeout: int = ib(default=None)
