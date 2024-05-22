from __future__ import annotations

from attr import dataclass, ib

from ..flow_object import FlowObject


@dataclass
class GPTAssistant(FlowObject):
    """
    ## GptAssistant

    This node allows to interact with the GPT Assistant API.

    * If you want to create a new assistant, you need to provide name, instructions, model parameters.
    * If you want to use an existing assistant, you need to provide assistant_id.

    content:

    ```yaml
        - id: g1
          type: gpt_assistant
          name: "GPT Assistant"
          instructions: "Please select an option"
          model: "gpt-3.5-turbo"
          assistant_id: "123456"
          api_key: "123456"
          variable: "gpt_response"
          user_input: "user_input"
          o_connection: "m1"
    ```
    """

    name: str = ib(default=None)
    instructions: str = ib(default=None)
    model: str = ib(default=None)
    assistant_id: str = ib(default=None)
    api_key: str = ib(factory=str)
    variable: str = ib(factory=str)
    user_input: str = ib(factory=str)
    o_connection: str = ib(factory=str)
