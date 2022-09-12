from __future__ import annotations

from typing import Dict, List

from aiohttp import ClientSession
from attr import dataclass, ib

from .input import Case
from .node import Node


@dataclass
class Response:
    cases: List[Case] = ib(metadata={"json": "cases"}, factory=list)


@dataclass
class HTTPRequest(Node):
    method: str = ib(metadata={"json": "method"})
    url: str = ib(metadata={"json": "url"})
    response: Response = ib(metadata={"json": "response"})
    variables: Dict = ib(metadata={"json": "variables"}, factory=dict)
    query_params: Dict = ib(metadata={"json": "variables"}, factory=dict)
    headers: Dict = ib(metadata={"json": "variables"}, factory=dict)
    data: Dict = ib(metadata={"json": "variables"}, factory=dict)

    async def request(self, session: ClientSession) -> None:

        response = await session.request(
            self.method, self.url, headers=self.headers, params=self.query_params, json=self.data
        )

        # response_data = await response.json()

        # for variable in self.variables:
