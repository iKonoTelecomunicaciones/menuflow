from typing import Dict

from aiohttp import BasicAuth, ClientTimeout, ContentTypeError
from mautrix.util.config import RecursiveDict
from ruamel.yaml.comments import CommentedMap

from ..db.room import RoomState
from ..middlewares import HTTPMiddleware
from ..repository import HTTPRequest as HTTPRequestModel
from .switch import Switch


class HTTPRequest(Switch):

    HTTP_ATTEMPTS: Dict = {}

    middleware: HTTPMiddleware = None

    def __init__(self, http_request_node_data: HTTPRequestModel) -> None:
        Switch.__init__(self, http_request_node_data)
        self.log = self.log.getChild(http_request_node_data.get("id"))
        self.data: Dict = http_request_node_data

    @property
    def method(self) -> str:
        return self.data.get("method", "")

    @property
    def url(self) -> str:
        return self.render_data(self.data.get("url", ""))

    @property
    def http_variables(self) -> Dict:
        return self.render_data(self.data.get("variables", {}))

    @property
    def cookies(self) -> Dict:
        return self.render_data(self.data.get("cookies", {}))

    @property
    def headers(self) -> Dict:
        return self.render_data(self.data.get("headers", {}))

    @property
    def basic_auth(self) -> Dict:
        return self.render_data(self.data.get("basic_auth", {}))

    @property
    def query_params(self) -> Dict:
        return self.render_data(self.data.get("query_params", {}))

    @property
    def body(self) -> Dict:
        return self.render_data(self.data.get("data", {}))

    @property
    def context_params(self) -> Dict[str, str]:
        return self.render_data(
            {
                "bot_mxid": "{{bot_mxid}}",
                "customer_room_id": "{{customer_room_id}}",
            }
        )

    def prepare_request(self) -> Dict:
        request_body = {}

        if self.query_params:
            request_body["params"] = self.query_params

        if self.basic_auth:
            request_body["auth"] = BasicAuth(
                login=self.basic_auth["login"],
                password=self.basic_auth["password"],
            )

        if self.headers:
            request_body["headers"] = self.headers

        if self.body:
            request_body["json"] = self.body

        return request_body

    async def make_request(self):
        """It makes a request to the URL specified in the node,
        and then it does some stuff with the response

        Returns
        -------
            The status code and the response text.
        """

        self.log.debug(f"Room {self.room.room_id} enters http_request node {self.id}")

        request_body = self.prepare_request()

        if self.middleware:
            self.middleware.room = self.room
            request_params_ctx = self.context_params
            request_params_ctx.update({"middleware": self.middleware})
        else:
            request_params_ctx = {}

        try:
            timeout = ClientTimeout(total=self.config["menuflow.timeouts.http_request"])
            response = await self.session.request(
                self.method,
                self.url,
                **request_body,
                trace_request_ctx=request_params_ctx,
                timeout=timeout,
            )
        except Exception as e:
            self.log.exception(f"Error in http_request node: {e}")
            o_connection = await self.get_case_by_id(id=str(500))
            await self.room.update_menu(node_id=o_connection, state=None)
            return 500, e

        self.log.debug(
            f"node: {self.id} method: {self.method} url: {self.url} status: {response.status}"
        )

        if response.status == 401:
            return response.status, await response.text()

        variables = {}
        o_connection = None

        if self.cookies:
            for cookie in self.cookies:
                variables[cookie] = response.cookies.output(cookie)

        try:
            response_data = await response.json()
        except ContentTypeError:
            response_data = {}

        if isinstance(response_data, dict):
            # Tulir and its magic since time immemorial
            serialized_data = RecursiveDict(CommentedMap(**response_data))
            if self.http_variables:
                for variable in self.http_variables:
                    try:
                        variables[variable] = self.render_data(
                            serialized_data[self.http_variables[variable]]
                        )
                    except KeyError:
                        pass
        elif isinstance(response_data, str):
            if self.http_variables:
                for variable in self.http_variables:
                    try:
                        variables[variable] = self.render_data(response_data)
                    except KeyError:
                        pass

                    break

        if self.cases:
            o_connection = await self.get_case_by_id(id=str(response.status))

        if o_connection:
            await self.room.update_menu(
                node_id=o_connection, state=RoomState.END if not self.cases else None
            )

        if variables:
            await self.room.set_variables(variables=variables)

        return response.status, await response.text()

    async def run_middleware(self, status: int, response: str):
        """If the HTTP status code is not 200 or 201,
        the function will log the response as an error. If the status code is 200 or 201,
        the function will reset the HTTP_ATTEMPTS dictionary.
        If the HTTP_ATTEMPTS dictionary has a key that matches the room ID,
        and the last HTTP node is the current node,
        and the number of attempts is greater than or equal to the number of attempts specified in
        the middleware, the function will reset the HTTP_ATTEMPTS dictionary and set the default
        connection as the active connection

        Parameters
        ----------
        status : int
            The HTTP status code returned by the server.
        response : str
            The response from the server.

        """

        if status == 401:
            self.HTTP_ATTEMPTS.update(
                {
                    self.room.room_id: {
                        "last_http_node": self.id,
                        "attempts_count": self.HTTP_ATTEMPTS.get(self.room.room_id, {}).get(
                            "attempts_count"
                        )
                        + 1
                        if self.HTTP_ATTEMPTS.get(self.room.room_id)
                        else 1,
                    }
                }
            )
            self.log.debug(
                "HTTP auth attempt"
                f"{self.HTTP_ATTEMPTS[self.room.room_id]['attempts_count']}, trying again ..."
            )

        if not status in [200, 201]:
            self.log.error(response)
        else:
            self.HTTP_ATTEMPTS.update(
                {self.room.room_id: {"last_http_node": None, "attempts_count": 0}}
            )

        if (
            self.HTTP_ATTEMPTS.get(self.room.room_id)
            and self.HTTP_ATTEMPTS[self.room.room_id]["last_http_node"] == self.id
            and self.HTTP_ATTEMPTS[self.room.room_id]["attempts_count"] >= self.middleware.attempts
        ):
            self.log.debug("Attempts limit reached, o_connection set as `default`")
            self.HTTP_ATTEMPTS.update(
                {self.room.room_id: {"last_http_node": None, "attempts_count": 0}}
            )
            await self.room.update_menu(await self.get_case_by_id("default"), None)

    async def run(self):
        """It makes a request to the URL specified in the node's configuration,
        and then runs the middleware
        """
        try:
            status, response = await self.make_request()
            self.log.info(f"http_request node {self.id} had a status of {status}")
        except Exception as e:
            self.log.exception(e)

        if self.middleware:
            await self.run_middleware(status=status, response=response)
