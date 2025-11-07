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

    async def update_flow(
        flow_db: FlowDB,
        incoming_flow: dict | None,
        flow_vars: dict,
        nodes: dict,
        positions: dict,
        current_tag: TagDB,
        config: Config,
        create_backup: bool = True,
    ) -> None:
        """
        Update existing flow with its modules and tags.

        Args:
            flow_db: Flow database instance to update
            incoming_flow: New flow structure (None if only updating vars)
            flow_vars: Flow variables to update
            nodes: Parsed nodes from incoming_flow
            positions: Module positions
            current_tag: Current tag for this flow
            config: Application config
            create_backup: Whether to create a backup before updating
        """
        if incoming_flow:
            modules = await DBModule.get_tag_modules(current_tag.id)

            # Update or delete existing modules
            if modules:
                for module_obj in modules:
                    name = module_obj.name
                    if name not in nodes:
                        await module_obj.delete()
                    else:
                        new_nodes = nodes.get(name, {}).get("nodes", [])
                        if module_obj.nodes != new_nodes:
                            module_obj.nodes = new_nodes
                        nodes.pop(name, None)

                        new_position = positions.pop(name, {})
                        if module_obj.position != new_position:
                            module_obj.position = new_position

                        await module_obj.update()

            # Create new modules
            for name, node in nodes.items():
                module_obj = DBModule(
                    flow_id=flow_db.id,
                    name=name,
                    nodes=node.get("nodes", []),
                    position=positions.get(name, {}),
                    tag_id=current_tag.id,
                )
                await module_obj.insert()

            # Create backup if requested and flow changed
            if create_backup and flow_db.flow != incoming_flow:
                await flow_db.backup_flow(config)

            flow_db.flow = incoming_flow

        # Update flow and tag
        flow_db.flow_vars = flow_vars
        current_tag.flow_vars = flow_vars

        await flow_db.update()
        await current_tag.update()
