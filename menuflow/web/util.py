from __future__ import annotations

import asyncio
import uuid
from copy import deepcopy
from logging import Logger, getLogger
from re import match
from textwrap import indent
from typing import Any, Dict, List

from ..config import Config
from ..db.client import Client as DBClient
from ..db.module import Module as DBModule
from ..menu import MenuClient

log: Logger = getLogger("menuflow.web.util")


class Util:
    """Class with utility functions."""

    @staticmethod
    def docstring(doc: str):
        """Decorator to add docstring to a function.

        Parameters
        ----------
        doc: str
            The docstring to add to the function.
        Returns
        -------
        function
            The function with the docstring added.
        """

        def wrapper(func):
            func.__doc__ = doc
            return func

        return wrapper

    @staticmethod
    def generate_uuid() -> str:
        """Generate a UUID for use in transactions.

        Returns:
            str: The UUID generated.
        """
        return uuid.uuid4().hex

    @staticmethod
    def parse_modules_for_module(
        module: list | dict,
        module_name: str,
    ) -> list | dict:
        """Parse a module object.

        Args:
            module (list | dict): The module to parse.
            module_name (str): The name of the module.

        Returns:
            list | dict: The parsed module object.
        """
        data = deepcopy(module)

        def update(d: dict):
            for node in d.get("nodes", []):
                node.setdefault("module", module_name)
            if d.get("position"):
                d["position"].setdefault("module", module_name)

        if isinstance(data, list):
            for item in data:
                update(item)
        else:
            update(data)

        return data

    @staticmethod
    def parse_module_to_flow_fmt(
        modules: list[dict],
    ) -> tuple[list, list]:
        """Parse a flow object.

        Returns:
            tuple[list, list]: The parsed flow object.
        """
        nodes = []
        positions = []
        data = deepcopy(modules)

        for module in data:
            if module.get("nodes"):
                for node in module.get("nodes"):
                    node.setdefault(
                        "module", module.get("name")
                    )  # setdefault is used to avoid an exception if the module name is not in the node
                nodes.extend(module.get("nodes"))
            if module.get("position"):
                module.get("position").setdefault("module", module.get("name"))
                positions.append(module.get("position"))

        return nodes, positions

    @staticmethod
    def parse_flow_to_module_fmt(
        flow: dict,
    ) -> tuple[dict, dict]:
        """Parse a flow object to a list of modules.

        Args:
            flow (dict): The flow object to parse.

        Returns:
            tuple[dict, dict]: The parsed flow object.
        """
        positions = {}
        flow_copy = deepcopy(flow)

        for position in flow_copy.get("modules", {}):
            name = position.pop("module")
            positions[name] = position

        nodes = {}

        for node in flow_copy.get("menu", {}).get("nodes", []):
            name = node.pop("module")
            if name not in nodes:
                nodes[name] = {"nodes": []}
            nodes[name]["nodes"].append(node)

        return nodes, positions

    @staticmethod
    def filter_nodes_by_keys(
        nodes: list[dict],
        keys_to_keep: list[str] = None,
    ) -> list[dict]:
        """keys_to_keep a list of nodes.

        Args:
            nodes (list[dict]): The list of nodes to keys_to_keep.
        """
        filtered_nodes = [
            {key: node[key] for key in keys_to_keep if key in node} for node in nodes
        ]
        return [node for node in filtered_nodes if node]

    @staticmethod
    def parse_template_indent(template: str, indent_level: int = None) -> str:
        """Get the example with the given indent level.

        Parameters
        ----------
        template: str
            The template to get the indent level from.
        indent_level: int
            The indent level to get the template with.

        Returns
        -------
        str
            The example with the given indent level.
        """
        lines = template.strip().splitlines()
        return lines[0] + "\n" + indent("\n".join(lines[1:]), " " * (indent_level or 20))

    @staticmethod
    async def update_flow_db_clients(
        flow_id: int, content: dict, config: Config, uuid: str
    ) -> None:
        """Update the flow of the db clients.

        Args:
            flow_id (int): The id of the flow to update.
            content (dict): The content of the flow to update.
            config (Config): The config of the flow to update.
        """

        db_clients = await DBClient.get_by_flow_id(flow_id)
        for db_client in db_clients:
            client = MenuClient.cache[db_client.id]
            await client.flow_cls.load_flow(flow_mxid=client.id, content=content, config=config)
            await Util.cancel_inactivity_tasks(
                client=client, config=config, metadata={"bot_mxid": client.id}, uuid=uuid
            )

    @staticmethod
    async def cancel_inactivity_tasks(
        client: MenuClient, config: Config, metadata: dict = None, uuid: str = None
    ) -> None:
        """Wait until no tasks with the given prefix are running."""
        metadata = metadata or {}
        regex_room_id = config["menuflow.regex.room_id"]
        cancelled_tasks = []

        for task in asyncio.all_tasks():
            if match(regex_room_id, task.get_name()) and all(
                getattr(task, "metadata", {}).get(k) == v for k, v in metadata.items()
            ):
                cancelled_tasks.append(task.get_name())
                task.cancel()

        if cancelled_tasks and config["menuflow.inactivity_options.recreate_on_save_flow"]:
            await client.matrix_handler.create_inactivity_tasks()
        else:
            log.debug(
                f"({uuid}) No previous inactivity tasks detected for bot {client.id}, "
                f"skipping inactivity tasks recreation"
            )

    @staticmethod
    async def validate_and_process_nodes(
        flow_id: int,
        nodes: List[Dict[str, Any]],
        allow_duplicates: bool = False,
    ) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
        """
        Validate and process nodes for module creation/import.

        Args:
            flow_id: The flow ID to check for existing nodes
            nodes: List of nodes to process
            allow_duplicates: If True, rename duplicate nodes; if False, raise error on duplicates

        Returns:
            tuple: (processed_nodes, node_id_mapping)
                - processed_nodes: List of nodes with potentially renamed IDs and names
                - node_id_mapping: Dictionary mapping original IDs to new IDs

        Raises:
            ValueError: If duplicates found and allow_duplicates is False
        """
        processed_nodes = []
        node_id_mapping = {}
        seen_ids = set()

        # Fetch all existing node IDs from the database in a single query
        existing_node_ids = await DBModule.get_all_node_ids(flow_id)

        for node in nodes:
            original_node_id = node.get("id")
            if not original_node_id:
                continue

            new_node = node.copy()
            new_node_id = original_node_id
            original_node_name = node.get("name", "")

            # Check for duplicates within the same module
            if original_node_id in seen_ids:
                if not allow_duplicates:
                    raise ValueError(
                        f"Node with ID '{original_node_id}' is repeated within the module"
                    )
                counter = 1
                while f"{original_node_id}_{counter}" in seen_ids:
                    counter += 1
                new_node_id = f"{original_node_id}_{counter}"

            # Check if node ID already exists in the flow
            if new_node_id in existing_node_ids:
                if not allow_duplicates:
                    raise ValueError(
                        f"Node with ID '{new_node_id}' already exists in module "
                        f"'{original_node_name}'"
                    )

                counter = 1
                while (
                    f"{original_node_id}_{counter}" in existing_node_ids
                    or f"{original_node_id}_{counter}" in seen_ids
                ):
                    counter += 1
                new_node_id = f"{original_node_id}_{counter}"

            # Update the node ID and name if it was changed
            if new_node_id != original_node_id:
                # Extract the suffix from the new_node_id
                suffix = new_node_id.replace(original_node_id, "")

                new_node["id"] = new_node_id

                # Also update the name field with the same suffix
                if original_node_name:
                    new_node["name"] = f"{original_node_name}{suffix}"

                node_id_mapping[original_node_id] = new_node_id
                log.debug(
                    f"Renamed node '{original_node_id}' to '{new_node_id}' "
                    f"and name '{original_node_name}' to '{new_node.get('name')}'"
                )

            seen_ids.add(new_node_id)
            processed_nodes.append(new_node)

        # Update references in nodes if they point to renamed nodes
        Util._update_node_references(processed_nodes, node_id_mapping)

        return processed_nodes, node_id_mapping

    @staticmethod
    def _update_node_references(
        nodes: List[Dict[str, Any]], node_id_mapping: Dict[str, str]
    ) -> None:
        """
        Update internal node references to point to renamed nodes.

        Args:
            nodes: List of nodes to update
            node_id_mapping: Dictionary mapping original IDs to new IDs
        """
        if not node_id_mapping:
            return

        for node in nodes:
            # Update common reference fields that might contain node IDs
            if "o_connection" in node and node["o_connection"] in node_id_mapping:
                node["o_connection"] = node_id_mapping[node["o_connection"]]

            # Update cases that might reference other nodes
            if "cases" in node and isinstance(node["cases"], list):
                for case in node["cases"]:
                    if isinstance(case, dict) and "o_connection" in case:
                        if case["o_connection"] in node_id_mapping:
                            case["o_connection"] = node_id_mapping[case["o_connection"]]

    @staticmethod
    async def create_module(
        flow_id: int,
        name: str,
        nodes: List[Dict[str, Any]],
        position: Dict[str, Any],
        allow_duplicates: bool = False,
    ) -> tuple[int, str, Dict[str, str], List[Dict[str, Any]]]:
        """
        Create a new module with validation and processing.

        Args:
            flow_id: The flow ID to create the module in
            name: The module name
            nodes: List of nodes for the module
            position: Position data for the module
            allow_duplicates: If True, rename duplicates; if False, raise error

        Returns:
            tuple: (module_id, final_name, node_id_mapping, processed_nodes)

        Raises:
            ValueError: If validation fails and allow_duplicates is False
        """
        # Fetch all existing module names
        existing_names = await DBModule.get_all_module_names(flow_id)

        # Get unique name if duplicates are allowed
        final_name = name
        if allow_duplicates:
            counter = 1
            while final_name in existing_names:
                final_name = f"{name}_{counter}"
                counter += 1
        elif name in existing_names:
            raise ValueError(f"Module with name '{name}' already exists in flow_id {flow_id}")

        # Process nodes
        processed_nodes, node_id_mapping = await Util.validate_and_process_nodes(
            flow_id, nodes, allow_duplicates
        )

        # Create the module
        new_module = DBModule(
            name=final_name,
            flow_id=flow_id,
            nodes=processed_nodes,
            position=position,
        )

        module_id = await new_module.insert()
        return module_id, final_name, node_id_mapping, processed_nodes
