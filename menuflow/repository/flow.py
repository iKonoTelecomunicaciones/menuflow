from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from attr import dataclass, ib
from mautrix.types import SerializableAttrs
from mautrix.util.logging import TraceLogger

from ..config import Config
from ..db import Flow as FlowDB
from ..db import Module as DBModule
from ..db import Tag as TagDB
from ..utils import Util

log: TraceLogger = logging.getLogger("menuflow.repository.flow")


@dataclass
class Flow(SerializableAttrs):
    nodes: List[Dict] = ib(factory=list)
    flow_variables: Dict[str, Any] = ib(default={})

    @classmethod
    async def load_from_db(cls, flow_mxid: str, config: Config) -> tuple[dict, list[dict]]:
        """
        Load a flow from the database.

        Args:
            flow_mxid (str): The mxid of the flow to load.

        Returns:
            tuple[dict, list[dict]]: The flow variables and nodes.
        """
        log.info(f"Loading flow {flow_mxid} from database")
        flow_db = await FlowDB.get_by_mxid(flow_mxid)
        tag_db = await TagDB.get_active_tag(flow_db.id)
        if not tag_db:
            log.error(f"No active tag found for flow {flow_mxid}")
            raise ValueError(f"No active tag found for flow {flow_mxid}")

        modules = await DBModule.get_tag_modules(tag_db.id)
        return tag_db.flow_vars, [node for module in modules for node in module.get("nodes", [])]

    @classmethod
    def load_from_yaml(cls, flow_mxid: str) -> tuple[dict, list[dict]]:
        """
        Load a flow from a YAML file.

        Args:
            flow_mxid (str): The mxid of the flow to load.

        Returns:
            tuple[dict, list[dict]]: The flow variables and nodes.
        """
        log.info(f"Loading flow {flow_mxid} from YAML file")
        path = Path(f"/data/flows/{flow_mxid}.yaml")
        if not path.exists():
            log.warning(f"File {flow_mxid}.yaml not found")
            path.write_text(yaml.dump(Util.flow_example()))
            log.warning(
                f"Example flow {flow_mxid}.yaml file was generated. "
                "Configure it and restart the service."
            )

        try:
            flow: Dict = yaml.safe_load(path.read_text())
            flow_data = flow["menu"]
        except Exception as e:
            log.exception(f"Error loading flow {flow_mxid}.yaml: {e}")
            raise

        return flow_data["flow_variables"], flow_data["nodes"]

    @classmethod
    async def load_flow(
        cls,
        flow_mxid: Optional[str] = None,
        content: Optional[Dict] = None,
        config: Optional[Config] = None,
    ) -> Flow:
        """
        Load a flow from a YAML file or from a dictionary getting from db.

        Args:
            flow_mxid (Optional[str]): The mxid of the flow to load.
            content (Optional[Dict]): The dictionary containing the flow.

        Returns:
            Flow: The loaded flow.
        """
        if content:
            flow_vars = content["flow_variables"]
            nodes = content["nodes"]
        elif flow_mxid:
            if config["menuflow.load_flow_from"] == "database":
                flow_vars, nodes = await cls.load_from_db(flow_mxid, config)
            else:
                flow_vars, nodes = cls.load_from_yaml(flow_mxid)

        return cls(flow_variables=flow_vars, nodes=nodes)
