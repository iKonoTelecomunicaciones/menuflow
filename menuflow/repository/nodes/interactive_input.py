from typing import Dict, List, Optional

from attr import dataclass, ib
from mautrix.types import BaseMessageEventContent, SerializableAttrs

from .input import Input


@dataclass
class ContentQuickReplay(SerializableAttrs):
    type: str = ib(default=None, metadata={"json": "type"})
    header: str = ib(default=None, metadata={"json": "header"})
    text: str = ib(default=None, metadata={"json": "text"})
    caption: str = ib(default=None, metadata={"json": "caption"})
    filename: str = ib(default=None, metadata={"json": "2"})
    url: str = ib(default=None, metadata={"json": "url"})


@dataclass
class InteractiveMessageOption(SerializableAttrs):
    type: str = ib(default=None, metadata={"json": "type"})
    title: str = ib(default=None, metadata={"json": "title"})
    description: str = ib(default=None, metadata={"json": "description"})
    postback_text: str = ib(default=None, metadata={"json": "postback_text"})


@dataclass
class ItemListReplay(SerializableAttrs):
    title: str = ib(default=None, metadata={"json": "title"})
    subtitle: str = ib(default=None, metadata={"json": "subtitle"})
    options: List[InteractiveMessageOption] = ib(metadata={"json": "options"}, factory=list)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            title=data.get("title"),
            subtitle=data.get("subtitle"),
            options=[InteractiveMessageOption(**option) for option in data.get("options", [])],
        )


@dataclass
class GlobalButtonsListReplay(SerializableAttrs):
    type: str = ib(default=None, metadata={"json": "type"})
    title: str = ib(default=None, metadata={"json": "title"})


@dataclass
class InteractiveMessageContent(SerializableAttrs):
    type: str = ib(default=None, metadata={"json": "type"})
    content: ContentQuickReplay = ib(default=None, metadata={"json": "content"})
    options: List[InteractiveMessageOption] = ib(metadata={"json": "options"}, factory=list)
    title: str = ib(default=None, metadata={"json": "title"})
    body: str = ib(default=None, metadata={"json": "body"})
    msgid: str = ib(default=None, metadata={"json": "msgid"})
    global_buttons: List[GlobalButtonsListReplay] = ib(
        metadata={"json": "global_buttons"}, factory=list
    )
    items: List[ItemListReplay] = ib(metadata={"json": "items"}, factory=list)

    @classmethod
    def from_dict(cls, data: Dict):
        if data["type"] == "quick_reply":
            return cls(
                type=data["type"],
                content=ContentQuickReplay(**data["content"]),
                options=[InteractiveMessageOption(**option) for option in data["options"]],
            )
        elif data["type"] == "list":
            return cls(
                type=data["type"],
                title=data["title"],
                body=data["body"],
                global_buttons=[
                    GlobalButtonsListReplay(**item) for item in data["global_buttons"]
                ],
                items=[ItemListReplay.from_dict(item) for item in data["items"]],
            )


@dataclass
class InteractiveMessage(SerializableAttrs, BaseMessageEventContent):
    msgtype: str = ib(default="none", metadata={"json": "msgtype"})
    body: str = ib(default=None, metadata={"json": "body"})
    interactive_message: InteractiveMessageContent = ib(
        factory=InteractiveMessageContent, metadata={"json": "interactive_message"}
    )

    @classmethod
    def from_dict(cls, msgtype: str, interactive_message: Dict, body: Optional[str] = ""):
        return cls(
            msgtype=msgtype,
            body=body,
            interactive_message=InteractiveMessageContent.from_dict(interactive_message),
        )


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
          validation_attempts: 3
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
                    url: "https://images.unsplash.com/photo-1575936123452-b67c3203c357?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxzZWFyY2h8Mnx8aW1hZ2V8ZW58MHx8MHx8fDA%3D&w=1000&q=80"
                    # If type = text set header parameter
                    header: "Gracias por comunicarte con iKono Telecomunicaciones."
                    text: "Para nosotros es un gusto poder ayudarte 😀"
                    caption: "Por favor selecciona una de las siguientes opciones:"
                options:
                  - type: "text",
                    title: "Sales"
                  - type: "text",
                    title: "Support"
                  - type: "text",
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
            validation_attempts: 3
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

    interactive_message: InteractiveMessageContent = ib(factory=InteractiveMessageContent)
