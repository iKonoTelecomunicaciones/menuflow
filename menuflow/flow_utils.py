import logging
from typing import Dict

from mautrix.util.logging import TraceLogger

from .middlewares.http import HTTPMiddleware
from .repository import FlowUtils as FlowUtilsModel
from .repository.middlewares import HTTPMiddleware, IRMMiddleware
from .repository.middlewares.email import EmailServer

log: TraceLogger = logging.getLogger("menuflow.flow_utils")


class FlowUtils:
    # Cache dicts
    middlewares_by_id: Dict[str, HTTPMiddleware | IRMMiddleware] = {}
    email_servers_by_id: Dict[str, EmailServer] = {}

    def __init__(self) -> None:
        self.data: FlowUtilsModel = FlowUtilsModel.load_flow_utils()

    def _add_middleware_to_cache(self, middleware_model: HTTPMiddleware | IRMMiddleware) -> None:
        self.middlewares_by_id[middleware_model.id] = middleware_model

    def _add_email_server_to_cache(self, email_server_model: EmailServer) -> None:
        self.email_servers_by_id[email_server_model.server_id] = email_server_model

    def get_middleware_by_id(self, middleware_id: str) -> HTTPMiddleware | IRMMiddleware | None:
        """This function retrieves a middleware by its ID from a cache or a list of middlewares.

        Parameters
        ----------
        middleware_id : str
            A string representing the ID of the middleware that needs to be retrieved.

        Returns
        -------
            This function returns a dictionary object representing a middleware in a graph, or `None`
            if the node with the given ID is not found.

        """

        try:
            return self.middlewares_by_id[middleware_id]
        except KeyError:
            pass

        try:
            for middleware in self.data.middlewares:
                if middleware_id == middleware.id:
                    self._add_middleware_to_cache(middleware)
                    return middleware
        except AttributeError:
            log.warning("No middlewares found in flow_utils.json")

    def get_email_servers(self) -> Dict[str, EmailServer]:
        try:
            for email_server in self.data.email_servers:
                self._add_email_server_to_cache(email_server)
        except AttributeError:
            log.warning("No email servers found in flow_utils.json")

        return self.email_servers_by_id
