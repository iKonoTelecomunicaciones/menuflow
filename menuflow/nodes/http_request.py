import asyncio
import json
from typing import TYPE_CHECKING

from aiohttp import BasicAuth, ClientTimeout, ContentTypeError
from jsonpath_ng import parse

from ..db.route import RouteState
from ..events import MenuflowNodeEvents
from ..events.event_generator import send_node_event
from ..repository import HTTPRequest as HTTPRequestModel
from ..room import Room
from ..utils import Nodes, Util
from .switch import Switch

if TYPE_CHECKING:
    from ..middlewares import HTTPMiddleware


class HTTPRequest(Switch):
    HTTP_ATTEMPTS: dict = {}

    middleware: "HTTPMiddleware" = None

    def __init__(
        self, http_request_node_data: HTTPRequestModel, room: Room, default_variables: dict
    ) -> None:
        Switch.__init__(
            self, http_request_node_data, room=room, default_variables=default_variables
        )
        self.log = self.log.getChild(http_request_node_data.get("id"))
        self.content: dict = http_request_node_data

    @property
    def method(self) -> str:
        return self.content.get("method", "")

    @property
    def url(self) -> str:
        return self.render_data(self.content.get("url", ""))

    @property
    def http_variables(self) -> dict:
        return self.render_data(self.content.get("variables", {}))

    @property
    def cookies(self) -> dict:
        return self.render_data(self.content.get("cookies", {}))

    @property
    def headers(self) -> dict:
        return self.render_data(self.content.get("headers", {}))

    @property
    def basic_auth(self) -> dict:
        return self.render_data(self.content.get("basic_auth", {}))

    @property
    def query_params(self) -> dict:
        return self.render_data(self.content.get("query_params", {}))

    @property
    def data(self) -> dict:
        return self.render_data(self.content.get("data", {}))

    @property
    def json(self) -> dict:
        body = self.content.get("json", "")
        if isinstance(body, dict):
            body = json.dumps(body)
        return self.render_data(body)

    @property
    def context_params(self) -> dict[str, str]:
        return self.render_data(
            {
                "bot_mxid": "{{ route.bot_mxid }}",
                "customer_room_id": "{{ route.customer_room_id }}",
            }
        )

    def prepare_request(self) -> dict:
        request_body = {}

        if query_params := self.query_params:
            request_body["params"] = query_params

        if basic_auth := self.basic_auth:
            request_body["auth"] = BasicAuth(
                login=basic_auth["login"],
                password=basic_auth["password"],
            )

        if headers := self.headers:
            request_body["headers"] = headers

        if data := self.data:
            request_body["data"] = data

        if json := self.json:
            request_body["json"] = json

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
            exception, status = None, 500
            timeout_config = self.config["menuflow.timeouts.http_request"]
            timeout = ClientTimeout(total=timeout_config)
            response = await self.session.request(
                self.method,
                self.url,
                **request_body,
                trace_request_ctx=request_params_ctx,
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            exception, status = "TimeoutError", 408
            self.log.warning(
                f"Request timeout after {timeout_config}s [method: {self.method}] [url: {self.url}]"
            )
        except Exception as e:
            exception, status = e, 500
            self.log.exception(f"Error in http_request node: {e}")

        if exception:
            o_connection = await self.get_case_by_id(id=status)
            await self.room.update_menu(node_id=o_connection, state=None)
            return status, exception, o_connection

        self.log.debug(
            f"node: {self.id} method: {self.method} url: {self.url} status: {response.status}"
        )

        if response.status >= 400:
            self.log.debug(f"Response: {await response.text()}")

        if response.status == 401:
            o_connection = None
            if not self.middleware:
                if self.cases:
                    o_connection = await self.get_case_by_id(id=response.status)

                if o_connection:
                    await self.room.update_menu(
                        node_id=o_connection, state=RouteState.END if not self.cases else None
                    )
            return response.status, None, o_connection

        variables = {}
        o_connection = None

        if cookies := self.cookies:
            for cookie in cookies:
                variables[cookie] = response.cookies.output(cookie)

        try:
            response_data: dict = await response.json()
            if response_data and isinstance(response_data, dict):
                response_data.update({"status": response.status})
        except ContentTypeError:
            response_data = await response.text()

        if isinstance(response_data, (dict, list, str)) and self.http_variables:
            for variable in self.http_variables:
                if isinstance(response_data, str):
                    try:
                        variables[variable] = self.render_data(response_data)
                    except KeyError:
                        pass
                    break
                else:
                    default_value = self.default_variables.get("flow").get("jq_default_value")
                    if not self.default_variables.get("flow").get("jq_syntax"):
                        try:
                            data_match = []
                            expr = parse(self.http_variables[variable])
                            data_match: list = [match.value for match in expr.find(response_data)]
                        except Exception as error:
                            self.log.error(
                                f"""Error parsing '{self.http_variables[variable]}' with jsonpath
                                on variable '{variable}'. Set to default value ({default_value}).
                                Error message: {error}"""
                            )
                    else:
                        jq_result: dict = Util.jq_compile(
                            self.http_variables[variable], response_data
                        )
                        if jq_result.get("status") != 200:
                            self.log.error(
                                f"""Error parsing '{self.http_variables[variable]}' with jq
                                on variable '{variable}'. Set to default value ({default_value}).
                                Error message: {jq_result.get("error")}, Status: {jq_result.get("status")}"""
                            )
                        data_match = jq_result.get("result")

                    try:
                        data_match = default_value if not data_match else data_match
                        variables[variable] = (
                            data_match if not data_match or len(data_match) > 1 else data_match[0]
                        )
                    except KeyError:
                        pass

        o_connection = await self.get_case_by_id(id=response.status)
        await self.room.update_menu(
            node_id=o_connection, state=RouteState.END if not self.cases else None
        )

        if variables:
            await self.room.set_variables(variables=variables)

        return response.status, await response.text(), o_connection

    async def run_middleware(self, status: int):
        """This function check athentication attempts to avoid an infinite try_athentication cicle.

        Parameters
        ----------
        status : int
            Http status of the request.

        """

        if status in [200, 201]:
            self.HTTP_ATTEMPTS.update(
                {self.room.room_id: {"last_http_node": None, "attempts_count": 0}}
            )
            return

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

        if status == 401:
            self.HTTP_ATTEMPTS.update(
                {
                    self.room.room_id: {
                        "last_http_node": self.id,
                        "attempts_count": (
                            self.HTTP_ATTEMPTS.get(self.room.room_id, {}).get("attempts_count") + 1
                            if self.HTTP_ATTEMPTS.get(self.room.room_id)
                            else 1
                        ),
                    }
                }
            )
            self.log.debug(
                "HTTP auth attempt "
                f"{self.HTTP_ATTEMPTS[self.room.room_id]['attempts_count']}, trying again ..."
            )

    async def run(self):
        """It makes a request to the URL specified in the node's configuration,
        and then runs the middleware
        """
        try:
            status, response, o_connection = await self.make_request()
            self.log.info(f"http_request node {self.id} had a status of {status}")
        except Exception as e:
            self.log.exception(e)

        if self.middleware:
            await self.run_middleware(status=status)

        await send_node_event(
            config=self.room.config,
            send_event=self.content.get("send_event"),
            event_type=MenuflowNodeEvents.NodeEntry,
            room_id=self.room.room_id,
            sender=self.room.matrix_client.mxid,
            node_type=Nodes.http_request,
            node_id=self.id,
            o_connection=o_connection,
            variables=self.room.all_variables | self.default_variables,
            conversation_uuid=await self.room.get_variable("room.conversation_uuid"),
        )
