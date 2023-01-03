from mautrix.client import Client as MatrixClient
from mautrix.types import Membership, MessageEvent, StrippedStateEvent

from .config import Config
from .flow import Flow
from .room import Room


class MatrixHandler(MatrixClient):
    def __init__(self, config: Config, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = config
        flow = Config(path=f"/data/flows/{self.mxid}.yaml", base_path="")
        flow.load()
        self.flow = Flow.deserialize(flow["menu"])

    async def handle_invite(self, evt: StrippedStateEvent) -> None:
        if evt.sender in self.config["menuflow.users_ignore"] or evt.sender == self.mxid:
            self.log.debug(f"This incoming invite event from {evt.room_id} will be ignored")
            return
        if evt.state_key == self.mxid and evt.content.membership == Membership.INVITE:
            await self.join_room(evt.room_id)

    async def handle_message(self, message: MessageEvent) -> None:

        self.log.debug(
            f"Incoming message [user: {message.sender}] [message: {message.content.body}] [room_id: {message.room_id}]"
        )

        # Message edits are ignored
        if message.content._relates_to and message.content._relates_to.rel_type:
            return

        # Ignore bot messages
        if message.sender in self.config["menuflow.users_ignore"] or message.sender == self.mxid:
            self.log.debug(
                f"This incoming message from {message.room_id} will be ignored :: {message.content.body}"
            )
            return

        try:
            room = await Room.get_by_room_id(room_id=message.room_id)
            room.config = self.config
        except Exception as e:
            self.log.exception(e)
            return

        if not room:
            return

        await self.algorithm(room=room, evt=message)

    async def algorithm(self, room: Room, evt: MessageEvent) -> None:
        """If the room is in the input state, then set the variable to the room's input,
        and if the node has an output connection, then update the menu to the output connection.
        Otherwise, run the node and update the menu to the output connection.
        If the node is an input node and the room is not in the input state,
        then show the message and update the menu to the node's id and set the state to input.
        If the node is a message node, then show the message and if the node has an output connection,
        then update the menu to the output connection and run the algorithm again

        Parameters
        ----------
        room : Room
            Room - the room object
        evt : MessageEvent
            The event that triggered the algorithm.

        Returns
        -------
            The return value is the result of the last expression in the function body.

        """

        # This is the case where the room is in the input state.
        # In this case, the variable is set to the room's input, and if the node has an output connection,
        # then the menu is updated to the output connection.
        # Otherwise, the node is run and the menu is updated to the output connection.

        node = self.flow.node(room=room)

        if node is None:
            self.log.debug(f"Room {room.room_id} does not have a node")
            await room.update_menu(node_id="start")
            return

        self.log.debug(f"The [room: {room.room_id}] [node: {node.id}] [state: {room.state}]")

        if room.state == "input":
            self.log.debug(f"Creating [variable: {node.variable}] [content: {evt.content.body}]")
            await room.set_variable(
                node.variable,
                int(evt.content.body) if evt.content.body.isdigit() else evt.content.body,
            )

            # If the node has an output connection, then update the menu to the output connection.
            # Otherwise, run the node and update the menu to the output connection.

            await room.update_menu(node_id=node.o_connection or await node.run())

        node = self.flow.node(room=room)

        if node.type == "switch":
            await room.update_menu(await node.run())

        node = self.flow.node(room=room)

        # This is the case where the room is not in the input state and the node is an input node.
        # In this case, the message is shown and the menu is updated to the node's id and the state is set to input.
        if node and node.type == "input" and room.state != "input":
            self.log.debug(f"Room {room.room_id} enters input node {node.id}")
            await node.show_message(room_id=room.room_id, client=self)
            await room.update_menu(node_id=node.id, state="input")
            return

        # Showing the message and updating the menu to the output connection.
        if node and node.type == "message":
            self.log.debug(f"Room {room.room_id} enters message node {node.id}")
            await node.show_message(room_id=room.room_id, client=self)

            await room.update_menu(
                node_id=node.o_connection, state="end" if not node.o_connection else None
            )

        node = self.flow.node(room=room)

        if node and node.type == "http_request":
            self.log.debug(f"Room {room.room_id} enters http_request node {node.id}")
            try:
                status, response = await node.request(session=self.api.session)
                self.log.info(f"http_request node {node.id} had a status of {status}")
                if not status in [200, 201]:
                    self.log.error(response)
            except Exception as e:
                self.log.exception(e)
                return

        node = self.flow.node(room=room)

        if room.state == "end":
            self.log.debug(f"The room {room.room_id} has terminated the flow")
            await room.update_menu(node_id="start")
            return

        await self.algorithm(room=room, evt=evt)
