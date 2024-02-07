from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from attr import dataclass, ib
from mautrix.types import SerializableAttrs
from mautrix.util.logging import TraceLogger

from ..utils import Util
from .middlewares import HTTPMiddleware, ASRMiddleware
from .nodes import CheckTime, HTTPRequest, Input, Message, Switch

log: TraceLogger = logging.getLogger("menuflow.repository.flow")


@dataclass
class Flow(SerializableAttrs):
    nodes: List[Message, Input, HTTPRequest, Switch, CheckTime] = ib(factory=list)
    middlewares: List[HTTPMiddleware | ASRMiddleware] = ib(default=[])
    flow_variables: Dict[str, Any] = ib(default={})

    @classmethod
    def load_flow(cls, flow_mxid: Optional[str] = None, content: Optional[Dict] = None) -> Flow:
        """
        Load a flow from a YAML file or from a dictionary.

        Args:
            flow_mxid (Optional[str]): The mxid of the flow to load.
            content (Optional[Dict]): The dictionary containing the flow.

        Returns:
            Flow: The loaded flow.
        """
        if flow_mxid:
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
        elif content:
            flow = content

        return cls(**flow["menu"])
