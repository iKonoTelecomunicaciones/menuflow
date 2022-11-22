from __future__ import annotations

from typing import Dict

from attr import dataclass, ib
from mautrix.types import SerializableAttrs

from ..user import User
from ..utils.base_logger import BaseLogger


@dataclass
class Node(SerializableAttrs, BaseLogger):
    id: str = ib(metadata={"json": "id"})
    type: str = ib(metadata={"json": "type"})
    user: User

    def build_node(self):
        return self.deserialize(self.__dict__)
