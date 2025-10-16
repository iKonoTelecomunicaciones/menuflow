from __future__ import annotations

from typing import Dict

from attr import dataclass, ib

from .base_event import BaseEvent


@dataclass
class NodeEntry(BaseEvent):
    room_id: str = ib(factory=str)
    node_type: str = ib(factory=str)
    node_id: str = ib(factory=str)
    o_connection: str = ib(default=None)
    variables: Dict = ib(factory=dict)
    conversation_uuid: str | None = ib(default=None)


@dataclass
class NodeInputData(BaseEvent):
    room_id: str = ib(factory=str)
    node_id: str = ib(factory=str)
    o_connection: str = ib(factory=str)
    variables: Dict = ib(factory=dict)
    conversation_uuid: str | None = ib(default=None)


@dataclass
class NodeInputTimeout(BaseEvent):
    room_id: str = ib(factory=str)
    node_id: str = ib(factory=str)
    o_connection: str = ib(factory=str)
    variables: Dict = ib(factory=dict)
    conversation_uuid: str | None = ib(default=None)
