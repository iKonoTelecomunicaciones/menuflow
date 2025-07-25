import uuid
from copy import deepcopy
from logging import Logger, getLogger
from textwrap import indent

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
