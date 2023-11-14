from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import yaml
from attr import dataclass, ib
from mautrix.types import SerializableAttrs
from mautrix.util.logging import TraceLogger

from ..utils import Util
from .middlewares import HTTPMiddleware
from .nodes import CheckTime, HTTPRequest, Input, Message, Switch

log: TraceLogger = logging.getLogger("menuflow.repository.flow")


@dataclass
class Flow(SerializableAttrs):
    nodes: List[Message, Input, HTTPRequest, Switch, CheckTime] = ib(factory=list)
    middlewares: List[HTTPMiddleware] = ib(default=[])
    flow_variables: Dict[str, Any] = ib(default={})

    @classmethod
    def load_flow(cls, flow_mxid: str) -> Flow:
        path = Path("/data/flows") / f"{flow_mxid}.yaml"
        if not path.exists():
            log.warning(f"File {flow_mxid}.yaml not found")
            path.write_text(yaml.dump(Util.flow_example()))
            log.warning(
                f"Example flow {flow_mxid}.yaml file was generated. "
                "Configure it and restart the service."
            )

        try:
            flow: Dict = yaml.safe_load(path.read_text())
        except Exception as e:
            log.exception(f"Error loading flow {flow_mxid}.yaml: {e}")
            raise

        return cls(**flow["menu"])
