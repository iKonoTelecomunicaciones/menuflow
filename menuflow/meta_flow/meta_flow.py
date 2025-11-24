import json
from asyncio import iscoroutine
from logging import Logger, getLogger

from mautrix.types import RoomID, UserID

from menuflow.db.route import RouteState
from menuflow.utils import Util as Util

from ..config import Config
from ..menu import MenuClient
from ..room import Room


class MetaFlow:
    log: Logger = getLogger("menuflow.api.meta")

    def __init__(self, user_id: UserID, room_id: RoomID, uuid: str, config: Config) -> None:
        self.user_id = user_id
        self.room_id = room_id
        self.uuid = uuid
        self.config = config

    async def execute_flow(self, data: dict) -> dict:
        client = await MenuClient.get(self.user_id)

        if not client or not client.enabled:
            self.log.error(f"({self.uuid}) -> Client {self.user_id} not found or not enabled")
            raise Exception(f"Client {self.user_id} not found or not enabled")

        self.log.critical(f"({self.uuid}) -> Client, flow: {self.user_id}")
        # Get the room instance
        room = await Room.get_by_room_id(self.room_id, self.user_id, create=False)

        if not room:
            self.log.error(f"({self.uuid}) -> Could not get room {self.room_id}")
            raise Exception(f"Could not access room {self.room_id}, perhaps it does not exist")

        flow_variables = Util.render_data(
            data=data,
            default_variables={},
            all_variables={},
        )

        await room.set_variables(flow_variables)

        self.log.critical(f"({self.uuid}) -> Room config: {self.config}?")
        if not hasattr(room, "config"):
            self.log.critical(f"({self.uuid}) -> Setting room config")
            room.config = self.config
            self.log.critical(f"({self.uuid}) -> Room config: {room.config}")

        # Get flow_id variable
        flow_id = data.get("screen", "")

        self.log.critical(
            f"########################################### room.route._variables: {room.route._variables}"
        )
        if data.get("data", {}).get("trigger") == room.route._variables.get("next"):
            flow_id = room.route._variables.get("next")

        self.log.critical(f"({self.uuid}) -> flow_id from data: {data}")

        # If flow_id doesn't exist, create it and use the initial node
        if not flow_id:
            self.log.error(
                f"({self.uuid}) -> Could not determine flow_id for flow in "
                f"client {self.user_id}"
            )
            raise Exception(
                f"Could not determine initial flow_id for flow in client {self.user_id}"
            )

        # Execute the node
        flow = client.flow_cls
        self.log.info(f"({self.uuid}) -> Executing flow node {flow_id} for client {client}")
        self.log.critical(
            f"({self.uuid}) -> Flow instance: {flow_id} {flow} node id: {room.route.node_id}"
        )

        # Get the current node
        node_data = flow.get_node_by_id(flow_id.lower())

        if not node_data:
            self.log.error(f"({self.uuid}) -> Node {flow_id} not found in flow")
            raise Exception(f"Node {flow_id} not found in flow")

        node_instance = flow.node(room=room, node_data=node_data)

        if not node_instance:
            self.log.error(f"({self.uuid}) -> Could not create node instance for {flow_id}")
            raise Exception(f"Could not create node instance for {flow_id}")

        # Execute the node
        next_node_id = await node_instance.run()

        # Get the next node from o_connection or node execution result
        if not next_node_id and iscoroutine(node_instance.o_connection):
            self.log.critical(f"({self.uuid}) -> o_connection is coroutine, awaiting...")
            next_node_id = await node_instance.o_connection
        elif not next_node_id:
            next_node_id = node_instance.o_connection

        self.log.critical(
            f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>({self.uuid}) -> next_node_id: {next_node_id}, room.route: {room.route}"
        )

        while not next_node_id or not room.route.state in (RouteState.START, RouteState.END):
            node_data = flow.get_node_by_id(next_node_id)

            if not node_data:
                self.log.error(f"({self.uuid}) -> Node {flow_id} not found in flow")
                break

            node_instance = flow.node(room=room, node_data=node_data)

            if not node_instance:
                self.log.error(
                    f"({self.uuid}) -> Could not create node instance for {next_node_id}"
                )
                break

            # Execute the node
            next_node_id = await node_instance.run()

            if (
                not next_node_id
                and hasattr(node_instance, "o_connection")
                and node_instance.o_connection
            ):
                next_node_id = await node_instance.o_connection

            self.log.critical(
                f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>({self.uuid}) -> Flow instance: {flow_id} {flow} node id: {room.route.node_id}"
            )

            self.log.critical(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>({self.uuid}) -> o_connection")

        self.log.info(
            f"({self.uuid}) -> Successfully executed node {flow_id}, next: {next_node_id}"
        )

        # Prepare response based on node execution
        # This is a basic response structure - you may need to adapt based on Meta's requirements
        try:
            response_data = json.loads(room.route.variables)
        except json.JSONDecodeError:
            self.log.error(
                f"({self.uuid}) -> Could not serialize room variables ({room.route.variables}) to JSON"
            )
            raise Exception("Could not serialize room variables to JSON")

        self.log.info(
            f"({self.uuid}) -> Successfully executed node {flow_id}, next: {next_node_id}"
        )
        self.log.info(f"({self.uuid}) -> room variables: {room.route}")

        if response_data.get("action"):
            del response_data["action"]

        if response_data.get("flow_token"):
            del response_data["flow_token"]

        if response_data.get("version"):
            del response_data["version"]

        self.log.critical(f"({self.uuid}) -> room.route.variables ---->: {room.route.variables}")
        self.log.critical(f"({self.uuid}) -> Response ---->: {response_data}")
        self.log.critical(f"({self.uuid}) -> Type Response---->: {type(response_data)}")

        return response_data
