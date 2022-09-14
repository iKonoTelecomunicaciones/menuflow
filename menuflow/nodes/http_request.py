from __future__ import annotations

from typing import Dict, Tuple

from aiohttp import ClientSession
from attr import dataclass, ib
from ruamel.yaml.comments import CommentedMap

from mautrix.util.config import RecursiveDict

from .input import Input


@dataclass
class HTTPRequest(Input):
    method: str = ib(default=None, metadata={"json": "method"})
    url: str = ib(default=None, metadata={"json": "url"})
    variables: Dict = ib(metadata={"json": "variables"}, factory=dict)
    query_params: Dict = ib(metadata={"json": "query_params"}, factory=dict)
    headers: Dict = ib(metadata={"json": "headers"}, factory=dict)
    data: Dict = ib(metadata={"json": "data"}, factory=dict)

    async def request(self, session: ClientSession) -> Tuple[str, Dict]:

        self.log.debug(self.variables)

        try:
            response = await session.request(
                self.method,
                self.url,
                headers=self.headers,
                params=self.query_params,
                data=self.data,
            )
        except Exception as e:
            self.log.exception(e)
            return

        # Tulir and its magic since time immemorial
        response_data = RecursiveDict(CommentedMap(**await response.json()))

        variables = {}
        o_connection = None

        for variable in self.variables.__dict__:
            variables[variable] = response_data[self.variables[variable]]

        if self.cases:
            o_connection = self.get_case_by_id(id=response.status)

        return o_connection, variables
