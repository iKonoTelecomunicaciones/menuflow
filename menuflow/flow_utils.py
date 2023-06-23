from typing import Dict

from .middlewares.http import HTTPMiddleware
from .repository import FlowUtils as FlowUtilsModel
from .repository.middlewares.email import EmailServer
from .repository.middlewares.http import HTTPMiddleware as HTTPMiddlewareModel


class FlowUtils:
    # Cache dicts
    middlewares_by_id: Dict[str, HTTPMiddlewareModel] = {}
    email_servers_by_id: Dict[str, EmailServer] = {}

    def __init__(self, flow_utils_model: FlowUtilsModel) -> None:
        self.data: FlowUtilsModel = flow_utils_model

    def _add_middleware_to_cache(self, middleware_model: HTTPMiddlewareModel):
        self.middlewares_by_id[middleware_model.id] = middleware_model

    def get_middleware_by_id(self, middleware_id: str) -> HTTPMiddleware | None:
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

        for middleware in self.data.middlewares:
            if middleware_id == middleware.get("id", ""):
                http_middleware = HTTPMiddlewareModel(**middleware)
                self._add_middleware_to_cache(http_middleware)
                return http_middleware

    def get_email_servers(self) -> Dict[str, EmailServer]:
        for email_server_data in self.data.email_servers:
            email_server = EmailServer(**email_server_data)
            self.email_servers_by_id[email_server.server_id] = email_server

        return self.email_servers_by_id
