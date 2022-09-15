from __future__ import annotations

from typing import Any, Dict

from attr import dataclass, ib

from mautrix.types import SerializableAttrs

from ..utils.base_logger import BaseLogger


@dataclass
class Node(SerializableAttrs, BaseLogger):
    id: str = ib(metadata={"json": "id"})
    type: str = ib(metadata={"json": "type"})
