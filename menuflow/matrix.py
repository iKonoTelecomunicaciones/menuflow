from mautrix.client import Client as MatrixClient
from mautrix.types import Membership, MessageEvent, StrippedStateEvent

from .config import Config
from .flow import Flow
from .user import User


class MatrixHandler(MatrixClient):
    def __init__(self, config: Config, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = config
        self.flow = Flow.deserialize(self.config["menu"])

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
            user = await User.get_by_mxid(mxid=message.sender)
            user.config = self.config

            if user.phone:
                await user.set_variable(variable_id="user_phone", value=user.phone)

        except Exception as e:
            self.log.exception(e)
            return

        if not user:
            return

        await self.algorithm(user=user, evt=message)

    async def algorithm(self, user: User, evt: MessageEvent) -> None:
        """If the user is in the input state, then set the variable to the user's input,
        and if the node has an output connection, then update the menu to the output connection.
        Otherwise, run the node and update the menu to the output connection.
        If the node is an input node and the user is not in the input state,
        then show the message and update the menu to the node's id and set the state to input.
        If the node is a message node, then show the message and if the node has an output connection,
        then update the menu to the output connection and run the algorithm again

        Parameters
        ----------
        user : User
            User - the user object
        evt : MessageEvent
            The event that triggered the algorithm.

        Returns
        -------
            The return value is the result of the last expression in the function body.

        """

        # This is the case where the user is in the input state.
        # In this case, the variable is set to the user's input, and if the node has an output connection,
        # then the menu is updated to the output connection.
        # Otherwise, the node is run and the menu is updated to the output connection.

        node = self.flow.node(user=user)

        if node is None:
            self.log.debug(f"User {user.mxid} does not have a node")
            await user.update_menu(node_id="start")
            return

        self.log.debug(f"The [user: {user.mxid}] [node: {node.id}] [state: {user.state}]")

        if user.state == "input":
            self.log.debug(f"Creating [variable: {node.variable}] [content: {evt.content.body}]")
            await user.set_variable(
                node.variable,
                int(evt.content.body) if evt.content.body.isdigit() else evt.content.body,
            )

            # If the node has an output connection, then update the menu to the output connection.
            # Otherwise, run the node and update the menu to the output connection.

            await user.update_menu(node_id=node.o_connection or await node.run())

        node = self.flow.node(user=user)

        if node.type == "switch":
            await user.update_menu(await node.run())

        node = self.flow.node(user=user)

        # This is the case where the user is not in the input state and the node is an input node.
        # In this case, the message is shown and the menu is updated to the node's id and the state is set to input.
        if node and node.type == "input" and user.state != "input":
            self.log.debug(f"User {user.mxid} enters input node {node.id}")
            await node.show_message(room_id=evt.room_id, client=self)
            await user.update_menu(node_id=node.id, state="input")
            return

        # Showing the message and updating the menu to the output connection.
        if node and node.type == "message":
            self.log.debug(f"User {user.mxid} enters message node {node.id}")
            await node.show_message(room_id=evt.room_id, client=self)

            await user.update_menu(
                node_id=node.o_connection, state="end" if not node.o_connection else None
            )

        node = self.flow.node(user=user)

        if node and node.type == "http_request":
            self.log.debug(f"User {user.mxid} enters http_request node {node.id}")
            try:
                status, response = await node.request(session=self.api.session)
                self.log.info(f"http_request node {node.id} had a status of {status}")
                if not status in [200, 201]:
                    self.log.error(response)
            except Exception as e:
                self.log.exception(e)
                return

        node = self.flow.node(user=user)

        if user.state == "end":
            self.log.debug(f"The user {user.mxid} has terminated the flow")
            await user.update_menu(node_id="start")
            return

        await self.algorithm(user=user, evt=evt)
