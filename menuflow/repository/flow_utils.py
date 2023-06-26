from __future__ import annotations

import logging
from typing import Dict, List

import yaml
from attr import dataclass, ib
from mautrix.types import SerializableAttrs
from mautrix.util.logging import TraceLogger

log: TraceLogger = logging.getLogger("menuflow.repository.flow_utils")


@dataclass
class FlowUtils(SerializableAttrs):
    middlewares: List[Dict] = ib(default=[])
    email_servers: List[Dict] = ib(default=[])

    @classmethod
    def load_flow_utils(cls):
        try:
            path = f"/data/flow_utils.yaml"
            with open(path, "r") as file:
                flow: Dict = yaml.safe_load(file)
            return cls(**flow)
        except FileNotFoundError:
            log.warning("File flow_utils.yaml not found")
