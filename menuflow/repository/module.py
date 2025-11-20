from __future__ import annotations

import logging
from typing import Any, Dict, List

from mautrix.util.logging import TraceLogger

from ..db.module import Module as DBModule

log: TraceLogger = logging.getLogger("menuflow.repository.module")


class ModuleRepository:
    """Repository for module operations with business logic."""

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
            if await DBModule.get_node_by_id(flow_id, new_node_id, False):
                if not allow_duplicates:
                    existing_node = await DBModule.get_node_by_id(flow_id, new_node_id, True)
                    raise ValueError(
                        f"Node with ID '{new_node_id}' already exists in module "
                        f"'{existing_node.get('module_name')}'"
                    )

                counter = 1
                while await DBModule.get_node_by_id(flow_id, f"{original_node_id}_{counter}", False):
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
        ModuleRepository._update_node_references(processed_nodes, node_id_mapping)

        return processed_nodes, node_id_mapping

    @staticmethod
    def _update_node_references(nodes: List[Dict[str, Any]], node_id_mapping: Dict[str, str]) -> None:
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
    async def get_unique_module_name(flow_id: int, original_name: str) -> str:
        """
        Get a unique module name by appending numbers if necessary.

        Args:
            flow_id: The flow ID to check for existing modules
            original_name: The original module name

        Returns:
            str: A unique module name
        """
        name = original_name
        counter = 1
        while await DBModule.check_exists_by_name(name, flow_id):
            name = f"{original_name}_{counter}"
            counter += 1
        return name

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
        # Get unique name if duplicates are allowed
        final_name = name
        if allow_duplicates:
            final_name = await ModuleRepository.get_unique_module_name(flow_id, name)
        elif await DBModule.check_exists_by_name(name, flow_id):
            raise ValueError(f"Module with name '{name}' already exists in flow_id {flow_id}")

        # Process nodes
        processed_nodes, node_id_mapping = await ModuleRepository.validate_and_process_nodes(
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
