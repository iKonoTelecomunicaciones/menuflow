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
        self.log.debug(
            f"({self.uuid}) -> MetaFlow instance created for user {user_id} in room {room_id}"
        )

    async def execute_flow(self, data: dict) -> dict:
        self.log.info(
            f"({self.uuid}) -> Starting execute_flow for user {self.user_id} in room {self.room_id}"
        )

        client = await MenuClient.get(self.user_id)

        if not client or not client.enabled:
            self.log.error(f"({self.uuid}) -> Client {self.user_id} not found or not enabled")
            raise Exception(f"Client {self.user_id} not found or not enabled")

        # Get the room instance
        room = await Room.get_by_room_id(self.room_id, self.user_id, create=False)

        if not room:
            self.log.error(f"({self.uuid}) -> Could not get room {self.room_id}")
            raise Exception(f"Could not access room {self.room_id}, perhaps it does not exist")

        flow_variables = Util.recursive_render(data=data)

        await room.set_variables(flow_variables)

        if not hasattr(room, "config"):
            self.log.debug(
                f"({self.uuid}) -> Setting config to room instance in room {self.room_id}"
            )
            room.config = self.config

        # Get flow_id variable
        flow_id = data.get("screen", "")
        self.log.debug(f"({self.uuid}) -> Initial flow_id from 'screen': {flow_id}")

        trigger_value = data.get("data", {}).get("trigger")
        next_value = room.route._variables.get("next")
        self.log.debug(
            f"({self.uuid}) -> Checking trigger match - trigger: {trigger_value}, next: {next_value} "
            f"in room {self.room_id} for client {self.user_id}"
        )

        if trigger_value == next_value:
            flow_id = next_value
            self.log.debug(
                f"({self.uuid}) -> Trigger matches next, using next value as flow_id: {flow_id}"
            )

        # If flow_id doesn't exist, create it and use the initial node
        if not flow_id:
            self.log.error(
                f"({self.uuid}) -> Could not determine flow_id for flow in "
                f"client {self.user_id}"
            )
            raise Exception(
                f"Could not determine initial flow_id for flow in client {self.user_id}"
            )

        self.log.debug(
            f"({self.uuid}) -> Final flow_id determined: {flow_id} for execution in room {self.room_id}"
        )

        # Execute the node
        flow = client.flow_cls
        self.log.info(
            f"({self.uuid}) -> Executing flow node {flow_id} for client {client} in room {room.room_id}"
        )

        # Get the current node
        self.log.debug(f"({self.uuid}) -> Getting node data for flow_id: {flow_id.lower()}")
        node_data = flow.get_node_by_id(flow_id.lower())

        if not node_data:
            self.log.error(f"({self.uuid}) -> Node {flow_id} not found in flow")
            raise Exception(f"Node {flow_id} not found in flow")

        node_instance = flow.node(room=room, node_data=node_data)

        if not node_instance:
            self.log.error(f"({self.uuid}) -> Could not create node instance for {flow_id}")
            raise Exception(f"Could not create node instance for {flow_id}")

        # Execute the node
        self.log.debug(
            f"({self.uuid}) -> Starting node execution: {flow_id} for room {self.room_id}"
        )
        next_node_id = await node_instance.run()
        self.log.debug(
            f"({self.uuid}) -> Node execution completed, returned next_node_id: {next_node_id} for room {self.room_id}"
        )

        # Get the next node from o_connection or node execution result
        self.log.debug(f"({self.uuid}) -> Checking o_connection for next node")
        if not next_node_id and iscoroutine(node_instance.o_connection):
            self.log.debug(f"({self.uuid}) -> o_connection is coroutine, awaiting...")
            next_node_id = await node_instance.o_connection
            self.log.debug(
                f"({self.uuid}) -> Awaited o_connection result: {next_node_id} for room {self.room_id}"
            )
        elif not next_node_id:
            next_node_id = node_instance.o_connection
            self.log.debug(f"({self.uuid}) -> Using o_connection directly: {next_node_id}")

        self.log.debug(
            f"({self.uuid}) -> Final next_node_id determined: {next_node_id} for room {self.room_id}"
        )
        self.log.debug(
            f"({self.uuid}) -> Matrix handler available for room {self.room_id}: {client.matrix_handler is not None}"
        )

        if next_node_id and not client.matrix_handler is None:
            self.log.debug(
                f"({self.uuid}) -> Executing matrix handler algorithm for next node: {next_node_id}"
            )
            await client.matrix_handler.algorithm(
                room=room,
                evt=None,
                process_evt=False,
                node_id=next_node_id,
            )

        self.log.info(
            f"({self.uuid}) -> Successfully executed node {flow_id}, next: {next_node_id} for client {self.user_id} in room {self.room_id}"
        )

        # Prepare response based on node execution
        # This is a basic response structure - you may need to adapt based on Meta's requirements
        self.log.debug(
            f"({self.uuid}) -> Preparing response from room variables in room {self.room_id}"
        )

        try:
            response_data = json.loads(room.route.variables)
        except json.JSONDecodeError as e:
            self.log.error(
                f"({self.uuid}) -> Could not serialize room variables ({room.route.variables}) to JSON: {e}"
            )
            raise Exception("Could not serialize room variables to JSON")

        self.log.info(
            f"({self.uuid}) -> Flow execution completed successfully, returning response data for user {self.user_id} in room {self.room_id}"
        )
        return response_data
