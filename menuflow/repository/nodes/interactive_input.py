import re

from attr import dataclass, ib
from mautrix.types import BaseMessageEventContent, SerializableAttrs

from .input import Input


@dataclass
class InteractiveMessage(SerializableAttrs, BaseMessageEventContent):
    msgtype: str = ib(default=None, metadata={"json": "msgtype"})
    body: str = ib(default="", metadata={"json": "body"})
    interactive_message: dict = ib(factory=dict, metadata={"json": "interactive_message"})

    def trim_reply_fallback(self) -> None:
        """
        Trim the reply fallback to avoid sending a message with the same content
        as the interactive message.
        """
        if not self.msgtype == "m.interactive_message":
            super().trim_reply_fallback()
            return

        if not self.interactive_message.get("body"):
            super().trim_reply_fallback()
            return

        self.interactive_message["body"] = re.sub(
            r"¬¬¬", r"", self.interactive_message.get("body", "")
        )
        super().trim_reply_fallback()


@dataclass
class InteractiveInput(Input):
    """
    ## Interactive Input
    An interactive input type node allows sending button and
    button list messages to whatsapp using Gupshup Bridge.

    Nota: This node is only available for whatsapp, matrix does not have support.

    content:

    ```yaml
        - id: i1
          type: interactive_input
          variable: opt
          validation: '{{ opt }}'
          validation_fail:
            message: "Please enter a valid option"
            attempts: 3
          inactivity_options:
              chat_timeout: 20 #seconds
              warning_message: "Message"
              time_between_attempts: 10 #seconds
              attempts: 3
          interactive_message:
                type: "quick_reply"
                content:
                    type: "image | text | video | document"
                    # If type = image | video | document set url parameter
                    url: "https://images.com/image.png"
                    # If type = text set header parameter
                    header: "Gracias por comunicarte con iKono Telecomunicaciones."
                    text: "Para nosotros es un gusto poder ayudarte 😀"
                    caption: "Por favor selecciona una de las siguientes opciones:"
                options:
                  - type: "text"
                    title: "Sales"
                  - type: "text"
                    title: "Support"
                  - type: "text"
                    title: "Development"
          cases:
            - id: "sales"
              o_connection: "m1"
            - id: "support"
              o_connection: "m2"
            - id: "development"
              o_connection: "m3"
            - id: "default"
              o_connection: "m4"
            - id: "timeout"
              o_connection: "m5"
            - id: "attempt_exceeded"
              o_connection: "m6"

          - id: i1
            type: interactive_input
            variable: opt
            validation: '{{ opt }}'
            validation_fail:
              message: "Please enter a valid option"
              attempts: 3
            inactivity_options:
                chat_timeout: 20 #seconds
                warning_message: "Message"
                time_between_attempts: 10 #seconds
                attempts: 3
            interactive_message:
                type: "list"
                title: "title text"
                body: "body text"
                msgid: "list1"
                global_buttons:
                  - type: "text",
                    title: "Global button"
                items:
                  - title: "first Section"
                    subtitle: "first Subtitle"
                    options:
                      - type: "text"
                          title: "section 1 row 1"
                          description: "first row of first section description"
                          postback_text: "1"
                      - type: "text"
                          title: "section 1 row 2"
                          description: "second row of first section description"
                          postback_text: "2"
                  - title: "Second Section"
                    subtitle: "Second Subtitle"
                    options:
                      - type: "text"
                          title: "section 2 row 1"
                          description: "first row of first section description"
                          postback_text: "3"
                      - type: "text"
                          title: "section 2 row 2"
                          description: "second row of first section description"
                          postback_text: "4"
            cases:
                - id: "1"
                  o_connection: "m1"
                - id: "2"
                  o_connection: "m2"
                - id: "3"
                  o_connection: "m3"
                - id: "4"
                  o_connection: "m4"
                - id: "default"
                  o_connection: "m5"
                - id: "timeout"
                  o_connection: "m6"
                - id: "attempt_exceeded"
                  o_connection: "m7"
    ```
    """

    interactive_message: dict = ib(factory=dict)
