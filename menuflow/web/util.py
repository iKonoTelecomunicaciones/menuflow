import uuid
from copy import deepcopy
from logging import Logger, getLogger

log: Logger = getLogger("menuflow.web.util")


class Util:
    """Class with utility functions."""

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
