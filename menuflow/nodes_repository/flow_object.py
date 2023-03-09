from __future__ import annotations

from typing import Any, Dict

from attr import dataclass, ib
from mautrix.types import SerializableAttrs

from ..utils.base_logger import BaseLogger


@dataclass
class FlowObject(SerializableAttrs, BaseLogger):
    id: str = ib()
    type: str = ib()
    flow_variables: Dict[str, Any] = {}
