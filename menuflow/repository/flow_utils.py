from __future__ import annotations

from typing import List, Dict

from attr import dataclass, ib
from mautrix.types import SerializableAttrs


@dataclass
class FlowUtils(SerializableAttrs):
    middlewares: List[Dict] = ib(default=[])
    email_servers: List[Dict] = ib(default=[])
